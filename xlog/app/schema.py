import datetime
import logging
import strawberry
import os
import json
import socket
import time

from typing import List, Optional
from pathlib import Path
from dotenv import load_dotenv
from app.config import Config
from rosetta import Events, Observables, Sender

from app.types.datafaker import (
    FakerTypeEnum, DataFakerInput, DataFakerOutput, DetailedScenarioStep,
    DetailedScenarioInput, DetailedScenarioOutput, ObservableTypeEnum,
    ObservableKnownEnum, GenerateObservablesInput, GenerateObservablesOutput,
    # v0.8.0 Phase 3 — dynamic schema override types
    SchemaOverrideInput, DataFakerOutputV2,
)
from app.types.sender import WorkerActionEnum, DataWorkerCreateInput, DataWorkerActionInput, WorkerOutput, \
    WorkerStatusOutput, ScenarioWorkerCreateInput, WorkerTypeEnum, ScenarioQueryWorkerCreateInput
from app.types.scenarios import ScenarioInput
from app.types.tech_stack import (
    TechnologyStack,
    TechnologyStackInput,
    stack_dict_to_type,
    input_to_dict,
)

from app.helper import scenario_sender_data
from app.webhook_worker import WebhookSender
from app import store
from app.dynamic_schema import generate_records_with_override

# Load environment variables from .env file if it exists
env_path = Path('.') / '.env'
if env_path.exists():
    load_dotenv()
XSIAM_URL = os.environ.get("XSIAM_URL")
XSIAM_ID = os.environ.get("XSIAM_ID")
XSIAM_KEY = os.environ.get("XSIAM_KEY")
WEBHOOK_ENDPOINT = os.environ.get("WEBHOOK_ENDPOINT")
WEBHOOK_KEY = os.environ.get("WEBHOOK_KEY")

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

workers = {}


def _enum_name(value):
    return getattr(value, "name", str(value))


def _record_simulation_run(
    *,
    name: str,
    kind: str,
    destination: str,
    worker_ids: List[str],
    tags=None,
    tactic=None,
    technique=None,
    procedure=None,
    metadata=None,
):
    try:
        return store.create_simulation_run(
            name=name,
            kind=kind,
            status="running",
            destination=destination,
            tags=tags or [],
            attack={
                "tactic": tactic,
                "technique": technique,
                "procedure": procedure,
            },
            worker_ids=worker_ids,
            summary=procedure,
            metadata=metadata or {},
        )
    except Exception as exc:
        logger.warning("Failed to persist simulation run state: %s", exc)
        return None


def _get_webhook_headers(key_override: Optional[str] = None):
    # key_override is the store-resolved xsiam_http auth_key injected by the
    # MCP log-destination resolver (v0.17.x). When absent, fall back to the
    # container-wide WEBHOOK_KEY env default (legacy behavior).
    # IMPORTANT: the Authorization header carries the RAW key, never
    # "Bearer <key>" — see xlog/CLAUDE.md "Webhook sender — non-Bearer auth
    # header". Reformatting breaks every existing customer integration.
    key = key_override or WEBHOOK_KEY
    if not key:
        raise ValueError(
            "An auth key is required for XSIAM_WEBHOOK destination "
            "(set WEBHOOK_KEY, or supply a store xsiam_http destination)."
        )
    return {"Authorization": key, "Content-Type": "application/json"}


def _get_host_ip() -> str:
    try:
        return socket.gethostbyname(socket.gethostname())
    except Exception:
        return "unknown"


def _build_webhook_payloads(items, event_type: str):
    payloads = []
    hostname = socket.gethostname()
    ip_address = _get_host_ip()
    for item in items:
        timestamp_ms = int(time.time() * 1000)
        severity = "info"
        metadata = None
        message = str(item)
        if isinstance(item, dict):
            metadata = dict(item)
            if "datetime_iso" in metadata:
                try:
                    timestamp = metadata.pop("datetime_iso")
                    datetime_obj = datetime.datetime.strptime(timestamp, "%Y-%m-%d %H:%M:%S.%f")
                    timestamp_ms = int(datetime_obj.timestamp() * 1000)
                except Exception:
                    pass
            severity_value = metadata.get("severity") or metadata.get("Severity")
            if severity_value:
                severity = str(severity_value).lower()
            message = metadata.get("message") or json.dumps(metadata)
        payload = {
            "timestamp": timestamp_ms,
            "hostname": hostname,
            "ip": ip_address,
            "event_type": event_type,
            "severity": severity,
            "message": message,
        }
        if metadata is not None:
            payload["metadata"] = metadata
        payloads.append(payload)
    return payloads


def _generate_worker_data(
    worker_type,
    count,
    datetime_obj,
    observables_obj,
    vendor,
    product,
    version,
    required_fields,
    fields,
):
    if worker_type == WorkerTypeEnum.SYSLOG:
        return Events.syslog(count=count, datetime_iso=datetime_obj, observables=observables_obj,
                             required_fields=required_fields)
    if worker_type == WorkerTypeEnum.CEF:
        return Events.cef(count=count, datetime_iso=datetime_obj, observables=observables_obj,
                          vendor=vendor, product=product, version=version,
                          required_fields=required_fields)
    if worker_type == WorkerTypeEnum.LEEF:
        return Events.leef(count=count, datetime_iso=datetime_obj, observables=observables_obj,
                           vendor=vendor, product=product, version=version,
                           required_fields=required_fields)
    if worker_type == WorkerTypeEnum.JSON:
        return Events.json(count=count, datetime_iso=datetime_obj, observables=observables_obj,
                           vendor=vendor, product=product, version=version,
                           required_fields=required_fields)
    if worker_type == WorkerTypeEnum.WINEVENT:
        return Events.winevent(count=count, datetime_iso=datetime_obj, observables=observables_obj)
    if worker_type == WorkerTypeEnum.Incident:
        return Events.incidents(count=count, fields=fields, datetime_iso=datetime_obj,
                                observables=observables_obj, vendor=vendor, product=product,
                                version=version, required_fields=required_fields)
    if worker_type == WorkerTypeEnum.XSIAM_Parsed:
        xsiam_alerts = []
        mandatory_fields = Config.XSIAM_MANDATORY_PARSED_FIELDS
        optional_fields = Config.XSIAM_OPTIONAL_PARSED_FIELDS
        total_fields = mandatory_fields + "," + optional_fields + ",vendor,product,event_timestamp"
        raw_data = Events.json(count=count, datetime_iso=datetime_obj, observables=observables_obj,
                               vendor=vendor, product=product, version=version,
                               required_fields=mandatory_fields)
        for item in raw_data:
            if "datetime_iso" in item:
                timestamp = item.pop("datetime_iso")
                datetime_obj = datetime.datetime.strptime(timestamp, "%Y-%m-%d %H:%M:%S.%f")
                item["event_timestamp"] = int(datetime_obj.timestamp() * 1000)
            new_item = {}
            for key in item.keys():
                if key in total_fields.split(","):
                    new_item[key] = item[key]
            xsiam_alerts.append(new_item)
        return xsiam_alerts
    if worker_type == WorkerTypeEnum.XSIAM_CEF:
        return Events.cef(count=count, datetime_iso=datetime_obj, observables=observables_obj,
                          vendor=vendor, product=product, version=version,
                          required_fields=required_fields)
    return []


@strawberry.type(description="Root query type.")
class Query:
    @strawberry.field(description="Return supported fields from the Rosetta library.")
    def get_supported_fields(self) -> List[str]:
        return list(Events.get_supported_fields())

    @strawberry.field(description="Generate fake data.")
    def generate_fake_data(self, request_input: DataFakerInput) -> DataFakerOutput:
        """
        Generate fake data based on the provided input.
        Args:
            request_input: Input object containing the type of fake data to generate and additional options.
        Returns:
            DataFakerOutput: Output object containing the generated fake data.
        """
        data = []
        vendor = request_input.vendor or "Phantom"
        if request_input.datetime_iso:
            datetime_obj = datetime.datetime.strptime(request_input.datetime_iso, "%Y-%m-%d %H:%M:%S")
        else:
            datetime_obj = None
        observables_init = Observables()
        observables = request_input.observables_dict
        required_fields = request_input.required_fields
        if required_fields:
            required_fields = ",".join([field.value for field in request_input.required_fields])
        if observables:
            observables_data = {}
            for key, value in observables.__dict__.items():
                if value is not None and key in observables_init.__dict__:
                    observables_data[key] = value
            observables_obj = Observables(**observables_data)
        else:
            observables_obj = None
        if request_input.type == FakerTypeEnum.SYSLOG:
            data = Events.syslog(count=request_input.count, datetime_iso=datetime_obj, observables=observables_obj,
                                required_fields=required_fields)
        elif request_input.type == FakerTypeEnum.CEF:
            data = Events.cef(count=request_input.count, datetime_iso=datetime_obj, observables=observables_obj,
                            vendor=vendor, product=request_input.product, version=request_input.version,
                            required_fields=required_fields)
        elif request_input.type == FakerTypeEnum.LEEF:
            data = Events.leef(count=request_input.count, datetime_iso=datetime_obj, observables=observables_obj,
                            vendor=vendor, product=request_input.product, version=request_input.version,
                            required_fields=required_fields)
        elif request_input.type == FakerTypeEnum.JSON:
            data = Events.json(count=request_input.count, datetime_iso=datetime_obj, observables=observables_obj,
                            vendor=vendor, product=request_input.product, version=request_input.version,
                            required_fields=required_fields)
        elif request_input.type == FakerTypeEnum.WINEVENT:
            data = Events.winevent(count=request_input.count, datetime_iso=datetime_obj, observables=observables_obj)
        elif request_input.type == FakerTypeEnum.Incident:
            data = Events.incidents(count=request_input.count, fields=request_input.fields, datetime_iso=datetime_obj,
                                    observables=observables_obj, vendor=vendor, product=request_input.product,
                                    version=request_input.version, required_fields=required_fields)
        elif request_input.type == FakerTypeEnum.XSIAM_Parsed:
            xsiam_alerts = []
            mandatory_fields = Config.XSIAM_MANDATORY_PARSED_FIELDS
            optional_fields = Config.XSIAM_OPTIONAL_PARSED_FIELDS
            total_fields = mandatory_fields+","+optional_fields+",vendor,product,event_timestamp"
            raw_data = Events.json(count=request_input.count, datetime_iso=datetime_obj, observables=observables_obj,
                                vendor=vendor, product=request_input.product, version=request_input.version,
                                required_fields=mandatory_fields)
            for item in raw_data:
                if "datetime_iso" in item:
                    timestamp = item.pop("datetime_iso")
                    datetime_obj = datetime.datetime.strptime(timestamp, "%Y-%m-%d %H:%M:%S")
                    event_timestamp = int(datetime_obj.timestamp() * 1000)
                    item["event_timestamp"] = event_timestamp
                new_item = {}
                for key in item.keys():
                    if key in total_fields.split(","):
                        new_item[key] = item[key]
                xsiam_alerts.append(new_item)
            data = xsiam_alerts

        # Log each entry generated
        logger.info(f"Generated {len(data)} {request_input.type} log entries.")

        return DataFakerOutput(
            data=data,
            type=request_input.type,
            count=request_input.count
        )

    @strawberry.field(
        description=(
            "v0.8.0 Phase 3 — Generate fake data with optional vendor-faithful "
            "schema override. When schema_override is None, behavior is identical "
            "to generate_fake_data (backward-compat). When schema_override is "
            "provided, emits records whose top-level keys match the vendor's "
            "actual field names from a Cortex ModelingRule schema."
        ),
    )
    def generate_fake_data_v2(
        self,
        request_input: DataFakerInput,
        schema_override: Optional[SchemaOverrideInput] = None,
    ) -> DataFakerOutputV2:
        """Vendor-faithful log simulation entry point (v0.8.0 Phase 3).

        Falls back to the legacy generate_fake_data path when no schema
        override is supplied. When schema_override is supplied, generates
        records via app/dynamic_schema.py — top-level keys are the vendor's
        own field names, values follow a type/name heuristic so Cortex's
        ModelingRule for the corresponding pack parses the output into XDM.
        """
        # Fallback path — no override supplied → use the existing
        # generate_fake_data implementation verbatim and wrap the result.
        if schema_override is None or not schema_override.vendor_fields:
            v1_out = self.generate_fake_data(request_input)
            return DataFakerOutputV2(
                data=v1_out.data,
                type=v1_out.type,
                count=v1_out.count,
                schema_applied=False,
                schema_dataset=None,
                vendor_field_count=None,
                fallback_reason=(
                    "no schema_override supplied — Rosetta path used"
                    if schema_override is None
                    else "schema_override.vendor_fields was empty"
                ),
            )

        # Override path — use dynamic_schema generator
        if request_input.datetime_iso:
            try:
                base_dt = datetime.datetime.strptime(
                    request_input.datetime_iso, "%Y-%m-%d %H:%M:%S"
                )
            except (ValueError, TypeError):
                base_dt = None
        else:
            base_dt = None

        # Carry over observables — caller can pin specific IPs/users from
        # threat-intel feeds. Treat the ObservablesInput as a dict keyed
        # by attribute name; values that aren't None are used as overrides
        # ONLY when a vendor field with the matching name is present.
        observable_overrides: dict = {}
        if request_input.observables_dict is not None:
            for key, value in request_input.observables_dict.__dict__.items():
                if value is None:
                    continue
                observable_overrides[key] = value

        count = request_input.count or 1
        records = generate_records_with_override(
            count=count,
            vendor_fields=schema_override.vendor_fields,
            base_datetime=base_dt,
            observable_overrides=observable_overrides,
            omit_meta=True,  # meta fields (_id/_time/_vendor) populated by the modeling rule at ingest
        )

        logger.info(
            f"Generated {len(records)} vendor-faithful records using "
            f"override pack={schema_override.pack_name} "
            f"rule={schema_override.rule_name} "
            f"dataset={schema_override.dataset_name} "
            f"({len(schema_override.vendor_fields)} vendor fields)"
        )

        return DataFakerOutputV2(
            data=records,
            type=request_input.type.value if request_input.type else "json",
            count=len(records),
            schema_applied=True,
            schema_dataset=schema_override.dataset_name,
            vendor_field_count=len(schema_override.vendor_fields),
            fallback_reason=None,
        )

    @strawberry.field(description="Generate fake scenario data based on the provided input.")
    def generate_scenario_fake_data(self, request_input: DetailedScenarioInput) -> DetailedScenarioOutput:
        """
        Generate fake data for a scenario with multiple steps and logs.
        
        Args:
            request_input: The input object containing the scenario details and log steps.
        
        Returns:
            DetailedScenarioOutput: The output object containing the generated fake data.
        """
        scenario_steps = []

        # Iterate over each step in the scenario
        for step in request_input.steps:
            step_data = {}
            step_data['tactic'] = step.tactic
            step_data['tactic_id'] = step.tactic_id
            step_data['technique'] = step.technique
            step_data['technique_id'] = step.technique_id
            step_data['procedure'] = step.procedure
            step_data['type'] = step.type
            step_data["logs"] = []

            # For each log in the step, generate fake data
            for log_input in step.logs:
                data = []
                vendor = log_input.vendor or "Phantom"
                if log_input.datetime_iso:
                    datetime_obj = datetime.datetime.strptime(log_input.datetime_iso, "%Y-%m-%d %H:%M:%S")
                else:
                    datetime_obj = None
                observables_init = Observables()
                observables = log_input.observables_dict
                required_fields = ",".join([field.value for field in log_input.required_fields]) if log_input.required_fields else ""

                # DEBUG LOGGING: Track observable processing
                logging.info(f"[PHANTOM-DEBUG] Raw observables from GraphQL: {observables}")
                logging.info(f"[PHANTOM-DEBUG] Required fields: {required_fields}")

                if observables:
                    observables_data = {}
                    for key, value in observables.__dict__.items():
                        if value is not None and key in observables_init.__dict__:
                            observables_data[key] = value
                        elif value is not None:
                            logging.warning(f"[PHANTOM-DEBUG] Observable key '{key}' NOT in Observables class, skipped!")

                    logging.info(f"[PHANTOM-DEBUG] Filtered observables_data: {observables_data}")
                    logging.info(f"[PHANTOM-DEBUG] Available Observables fields: {list(observables_init.__dict__.keys())[:50]}")

                    observables_obj = Observables(**observables_data)
                else:
                    observables_obj = None
                if log_input.type == FakerTypeEnum.SYSLOG:
                    data = Events.syslog(count=log_input.count, datetime_iso=datetime_obj, observables=observables_obj,
                                        required_fields=required_fields)
                elif log_input.type == FakerTypeEnum.CEF:
                    data = Events.cef(count=log_input.count, datetime_iso=datetime_obj, observables=observables_obj,
                                    vendor=vendor, product=log_input.product, version=log_input.version,
                                    required_fields=required_fields)
                elif log_input.type == FakerTypeEnum.LEEF:
                    data = Events.leef(count=log_input.count, datetime_iso=datetime_obj, observables=observables_obj,
                                    vendor=vendor, product=log_input.product, version=log_input.version,
                                    required_fields=required_fields)
                elif log_input.type == FakerTypeEnum.WINEVENT:
                    data = Events.winevent(count=log_input.count, datetime_iso=datetime_obj, observables=observables_obj)
                elif log_input.type == FakerTypeEnum.JSON:
                    data = Events.json(count=log_input.count, datetime_iso=datetime_obj, observables=observables_obj,
                                    vendor=vendor, product=log_input.product, version=log_input.version,
                                    required_fields=required_fields)
                elif log_input.type == FakerTypeEnum.Incident:
                    data = Events.incidents(count=log_input.count, fields=log_input.fields, datetime_iso=datetime_obj,
                                            observables=observables_obj, vendor=vendor, product=log_input.product,
                                            version=log_input.version, required_fields=required_fields)
                elif log_input.type == FakerTypeEnum.XSIAM_Parsed:
                    xsiam_alerts = []
                    mandatory_fields = Config.XSIAM_MANDATORY_PARSED_FIELDS
                    optional_fields = Config.XSIAM_OPTIONAL_PARSED_FIELDS
                    total_fields = mandatory_fields+","+optional_fields+",vendor,product,event_timestamp"
                    raw_data = Events.json(count=log_input.count, datetime_iso=datetime_obj, observables=observables_obj,
                                        vendor=vendor, product=log_input.product, version=log_input.version,
                                        required_fields=mandatory_fields)
                    for item in raw_data:
                        if "datetime_iso" in item:
                            timestamp = item.pop("datetime_iso")
                            datetime_obj = datetime.datetime.strptime(timestamp, "%Y-%m-%d %H:%M:%S.%f")
                            event_timestamp = int(datetime_obj.timestamp() * 1000)
                            item["event_timestamp"] = event_timestamp
                        new_item = {}
                        for key in item.keys():
                            if key in total_fields.split(","):
                                new_item[key] = item[key]
                        xsiam_alerts.append(new_item)
                    data = xsiam_alerts

                logger.info(f"Generated {len(data)} {log_input.type} log entries of scenario: {request_input.name}.")

                # Append the generated fake data to the step data
                step_data["logs"].append(data)
            
            # Add step data to the scenario data
            scenario_steps.append(step_data)

        return DetailedScenarioOutput(
            name=request_input.name,
            tags=request_input.tags,
            steps=scenario_steps
        )

    @strawberry.field(description="Create a data worker.")
    def create_data_worker(self, request_input: DataWorkerCreateInput) -> WorkerOutput:
        """
        Create a data worker for sending fake data.

        Args:
            request_input: Input object containing the options for creating a data worker.

        Returns:
            DataWorkerOutput: Output object containing information about the created data worker.

        v0.12.0 R3.A — when `request_input.schema_override` is supplied
        AND `destination` is a `udp:` or `tcp:` URI, the resolver routes
        through `OverrideSender` (xlog/app/override_sender.py). That
        sender uses `generate_records_with_override()` per tick to emit
        records whose top-level keys match the vendor's actual field
        names. XSIAM / XSIAM_WEBHOOK destinations continue to use the
        existing Sender / WebhookSender paths (schema_override is
        ignored — those paths have their own format normalization).
        """
        global workers
        active_workers = {}
        for worker_id, worker in workers.items():
            if worker.status == 'Running':
                active_workers[worker_id] = worker
        workers = active_workers
        if len(workers.keys()) >= int(Config.WORKERS_NUMBER):
            raise Exception("All workers are busy, please stop a running worker.")
        now = datetime.datetime.now()
        worker_name = f"worker_{now.strftime('%Y%m%d%H%M%S')}"

        # v0.12.0 R3.A — schema-override short-circuit. Route to
        # OverrideSender BEFORE the legacy destination branches when
        # the caller supplied vendor_fields for a UDP/TCP destination.
        override = request_input.schema_override
        if (
            override is not None
            and override.vendor_fields
            and request_input.destination
            and (request_input.destination.startswith("udp:") or request_input.destination.startswith("tcp:"))
        ):
            from app.override_sender import OverrideSender
            # Carry observables_dict through as forced field values. The
            # inline generate_fake_data_v2 path already builds these; the
            # streaming OverrideSender path silently dropped them pre-
            # v0.17.105 — which meant multi-dataset discriminators
            # (eventType / Workload / category / Operation) never reached
            # the generated record, so sibling datasets (okta_sso_raw,
            # o365_*_raw, azure_ad_*_raw, azure_aks_raw) couldn't route.
            override_obs: dict = {}
            _obs = request_input.observables_dict
            if _obs is not None:
                _items = _obs.items() if hasattr(_obs, "items") else _obs.__dict__.items()
                for _k, _v in _items:
                    if _v is not None:
                        override_obs[_k] = _v
            data_worker = OverrideSender(
                worker_name=worker_name,
                data_type=request_input.type.name,
                destination=request_input.destination,
                vendor_fields=override.vendor_fields,
                count=int(request_input.count),
                interval=int(request_input.interval),
                verify_ssl=request_input.verify_ssl,
                vendor=request_input.vendor,
                product=request_input.product,
                observable_overrides=override_obs,
            )
            workers[worker_name] = data_worker
            data_worker.start()
            _record_simulation_run(
                name=worker_name,
                kind="worker",
                destination=request_input.destination,
                worker_ids=[worker_name],
                metadata={
                    "log_type": _enum_name(request_input.type),
                    "vendor": request_input.vendor,
                    "product": request_input.product,
                    "count": request_input.count,
                    "interval": request_input.interval,
                    "schema_override": True,
                    "vendor_field_count": len(override.vendor_fields),
                    "pack_name": override.pack_name,
                    "rule_name": override.rule_name,
                    "dataset_name": override.dataset_name,
                },
            )
            return WorkerOutput(
                type=request_input.type.name,
                worker=worker_name,
                status=data_worker.status,
                count=str(request_input.count),
                interval=str(request_input.interval),
                verifySsl=str(request_input.verify_ssl),
                destination=request_input.destination,
                createdAt=str(data_worker.created_at),
            )

        if request_input.datetime_iso:
            datetime_obj = datetime.datetime.strptime(request_input.datetime_iso, "%Y-%m-%d %H:%M:%S")
        else:
            datetime_obj = None
        observables_init = Observables()
        observables = request_input.observables_dict
        if observables:
            observables_data = {}
            for key, value in observables.items():
                if value is not None and key in observables_init.__dict__:
                    observables_data[key] = value
            observables_obj = Observables(**observables_data)
        else:
            observables_obj = None
        required_fields = request_input.required_fields
        vendor = request_input.vendor or "Phantom"
        if request_input.destination == "XSIAM":
            headers = {
                "Authorization": XSIAM_KEY,
                "x-xdr-auth-id": XSIAM_ID
            }
            xsiam_alerts = []
            if request_input.type == WorkerTypeEnum.JSON:

                xsiam_destination = XSIAM_URL + "/public_api/v1/alerts/insert_parsed_alerts"
                mandatory_fields = Config.XSIAM_MANDATORY_PARSED_FIELDS
                optional_fields = Config.XSIAM_OPTIONAL_PARSED_FIELDS
                total_fields = mandatory_fields+","+optional_fields+",vendor,product,event_timestamp"
                raw_data = Events.json(count=request_input.count, datetime_iso=datetime_obj, observables=observables_obj,
                                    vendor=vendor, product=request_input.product, version=request_input.version,
                                    required_fields=mandatory_fields)
                for item in raw_data:
                    if "datetime_iso" in item:
                        timestamp = item.pop("datetime_iso")
                        datetime_obj = datetime.datetime.strptime(timestamp, "%Y-%m-%d %H:%M:%S.%f")
                        event_timestamp = int(datetime_obj.timestamp() * 1000)
                        item["event_timestamp"] = event_timestamp
                    new_item = {}
                    for key in item.keys():
                        if key in total_fields.split(","):
                            new_item[key] = item[key]
                    xsiam_alerts.append(new_item)
                data_json = {
                    "request_data": {
                        "alerts": xsiam_alerts
                    }
                }
                data_worker = Sender(worker_name=worker_name, data_type="JSON",
                                     destination=xsiam_destination, data_json=data_json,
                                     verify_ssl=request_input.verify_ssl, headers=headers)
            else:
                xsiam_destination = XSIAM_URL + "/public_api/v1/alerts/insert_cef_alerts"
                xsiam_alerts = Events.cef(count=request_input.count, datetime_iso=datetime_obj,
                                          observables=observables_obj, vendor=vendor, product=request_input.product,
                                          version=request_input.version, required_fields=request_input.required_fields)
                data_json = {
                    "request_data": {
                        "alerts": xsiam_alerts
                    }
                }
                data_worker = Sender(worker_name=worker_name, data_type="JSON",
                                     destination=xsiam_destination, data_json=data_json,
                                     verify_ssl=request_input.verify_ssl, headers=headers)
        elif request_input.destination == "XSIAM_WEBHOOK":
            # v0.17.x store-driven resolution: prefer the per-destination
            # endpoint + auth key injected by the MCP resolver (xsiam_http
            # log-destination); fall back to the container-wide env defaults
            # when the worker was created without a store destination.
            webhook_endpoint = request_input.webhook_url or WEBHOOK_ENDPOINT
            if not webhook_endpoint:
                raise ValueError(
                    "A webhook endpoint is required for XSIAM_WEBHOOK destination "
                    "(set WEBHOOK_ENDPOINT, or supply a store xsiam_http destination)."
                )
            headers = _get_webhook_headers(request_input.webhook_key)
            data = _generate_worker_data(
                request_input.type,
                request_input.count,
                datetime_obj,
                observables_obj,
                vendor,
                request_input.product,
                request_input.version,
                required_fields,
                request_input.fields,
            )
            event_type = f"phantom_{request_input.type.name.lower()}"
            payloads = _build_webhook_payloads(data, event_type=event_type)
            data_worker = WebhookSender(
                worker_name=worker_name,
                destination=webhook_endpoint,
                payloads=payloads,
                interval=request_input.interval,
                verify_ssl=request_input.verify_ssl,
                headers=headers,
            )
        else:
            data_worker = Sender(worker_name=worker_name, data_type=request_input.type.name,
                                 count=int(request_input.count), destination=request_input.destination,
                                 vendor=vendor, product=request_input.product, version=request_input.version,
                                 observables=observables_obj, interval=int(request_input.interval),
                                 datetime_obj=datetime_obj, required_fields=required_fields,
                                 fields=request_input.fields, verify_ssl=request_input.verify_ssl)
        workers[worker_name] = data_worker
        data_worker.start()
        _record_simulation_run(
            name=worker_name,
            kind="worker",
            destination=request_input.destination,
            worker_ids=[worker_name],
            metadata={
                "log_type": _enum_name(request_input.type),
                "vendor": vendor,
                "product": request_input.product,
                "count": request_input.count,
                "interval": request_input.interval,
            },
        )
        return WorkerOutput(type=data_worker.data_type, worker=data_worker.worker_name, status=data_worker.status,
                            count=data_worker.count, interval=data_worker.interval,
                            destination=data_worker.destination, verifySsl=str(data_worker.verify_ssl),
                            createdAt=str(data_worker.created_at))

    @strawberry.field(description="Create a scenario worker from file.")
    def create_scenario_worker(self, request_input: ScenarioWorkerCreateInput) -> List[WorkerOutput]:
        """
        Create a scenario worker for sending fake data.

        Args:
            request_input: Input object containing the options for creating a data worker.

        Returns:
            WorkerOutput: Output object containing information about the created data worker.

        """
        global workers
        scenario_workers_output = []
        active_workers = {}
        for worker_id, worker in workers.items():
            if worker.status == 'Running':
                active_workers[worker_id] = worker
        workers = active_workers
        if len(workers.keys()) >= int(Config.WORKERS_NUMBER):
            raise Exception("All workers are busy, please stop a running worker.")
        if request_input.datetime_iso:
            datetime_obj = datetime.datetime.strptime(request_input.datetime_iso, "%Y-%m-%d %H:%M:%S")
        else:
            datetime_obj = None
        vendor = request_input.vendor or "Phantom"
        try:
            with open(f'scenarios/ready/{request_input.scenario}.json', 'r') as file:
                scenario_tactics = json.load(file)['tactics']
        except FileNotFoundError:
            raise FileNotFoundError(f"The scenario: '{request_input.scenario}' file does not exist.")
        except json.JSONDecodeError as e:
            raise ValueError(f"Error decoding JSON in scenario file '{request_input.scenario}.json': {str(e)}")

        if scenario_tactics:
            for tactic in scenario_tactics:
                now = datetime.datetime.now()
                worker_name = f"worker_{now.strftime('%Y%m%d%H%M%S')}"
                interval = tactic.get('interval') or 1
                count = tactic.get('count') or 1
                observables_init = Observables()
                observables = tactic['log'].get('observables')
                if observables:
                    observables_data = {}
                    for key, value in observables.items():
                        if value is not None and key in observables_init.__dict__:
                            observables_data[key] = value
                    observables_obj = Observables(**observables_data)
                else:
                    observables_obj = None
                logger.info(f"Creating worker for type={tactic.get('type')}, count={count}, destination={request_input.destination}")
                logger.info(f"Observables: {observables_obj}, Required Fields: {tactic.get('required_fields')}")
                if request_input.destination == "XSIAM_WEBHOOK":
                    headers = _get_webhook_headers()
                    data = _generate_worker_data(
                        WorkerTypeEnum[tactic['type']],
                        count,
                        datetime_obj,
                        observables_obj,
                        vendor,
                        tactic['log'].get('product'),
                        tactic['log'].get('version'),
                        tactic.get('required_fields'),
                        tactic.get('fields'),
                    )
                    event_type = f"phantom_{tactic['type'].lower()}"
                    payloads = _build_webhook_payloads(data, event_type=event_type)
                    scenario_worker = WebhookSender(
                        worker_name=worker_name,
                        destination=WEBHOOK_ENDPOINT,
                        payloads=payloads,
                        interval=interval,
                        verify_ssl=request_input.verify_ssl,
                        headers=headers,
                    )
                else:
                    scenario_worker = Sender(worker_name=worker_name, data_type=tactic['type'],
                                             count=count, destination=request_input.destination,
                                             vendor=vendor, product=tactic['log'].get('product'),
                                             version=tactic['log'].get('version'), observables=observables_obj,
                                             interval=interval, datetime_obj=datetime_obj,
                                             required_fields=tactic.get('required_fields'),
                                             fields=tactic.get('fields'))
                workers[worker_name] = scenario_worker
                scenario_worker.start()
                scenario_workers_output.append(WorkerOutput(type=scenario_worker.data_type,
                                                            worker=scenario_worker.worker_name,
                                                            status=scenario_worker.status,
                                                            count=scenario_worker.count,
                                                            interval=scenario_worker.interval,
                                                            destination=scenario_worker.destination,
                                                            verifySsl=str(scenario_worker.verify_ssl),
                                                            createdAt=str(scenario_worker.created_at)))
        if scenario_workers_output:
            first_tactic = scenario_tactics[0] if scenario_tactics else {}
            _record_simulation_run(
                name=request_input.scenario,
                kind="scenario",
                destination=request_input.destination,
                worker_ids=[item.worker for item in scenario_workers_output],
                tags=["scenario", request_input.scenario],
                tactic=first_tactic.get("tactic"),
                technique=first_tactic.get("technique") or first_tactic.get("technique_id"),
                procedure=first_tactic.get("procedure"),
                metadata={
                    "source": "scenario_file",
                    "scenario": request_input.scenario,
                    "steps": len(scenario_tactics),
                    "vendor": vendor,
                },
            )
            try:
                store.create_scenario_package(
                    name=request_input.scenario,
                    status="active",
                    tags=["scenario", request_input.scenario],
                    attack={
                        "tactic": first_tactic.get("tactic"),
                        "technique": first_tactic.get("technique") or first_tactic.get("technique_id"),
                        "procedure": first_tactic.get("procedure"),
                    },
                    telemetry={"worker_ids": [item.worker for item in scenario_workers_output]},
                    metadata={"source": "scenario_file"},
                )
            except Exception as exc:
                logger.warning("Failed to persist scenario package: %s", exc)
        return scenario_workers_output

    @strawberry.field(description="Create a scenario worker from query.")
    def create_scenario_worker_from_query(self, request_input: ScenarioQueryWorkerCreateInput) -> List[WorkerOutput]:
        """
        Create scenario workers for sending fake data based on scenario steps provided in the request input.

        Args:
            request_input: Input object containing the options for creating data workers, including scenario steps.

        Returns:
            List[WorkerOutput]: Output list containing information about the created data workers.
        """

        global workers
        scenario_workers_output = []
        active_workers = {}

        # Clean up inactive workers
        for worker_id, worker in workers.items():
            if worker.status == 'Running':
                active_workers[worker_id] = worker
        workers = active_workers

        # Check if maximum number of workers is reached
        if len(workers.keys()) >= int(Config.WORKERS_NUMBER):
            raise Exception("All workers are busy, please stop a running worker.")

        # Get scenario steps from request_input
        scenario_steps = request_input.steps

        if scenario_steps:
            for step in scenario_steps:
                # Each step may have multiple logs
                for log_input in step.logs:
                    now = datetime.datetime.now()
                    worker_name = f"worker_{now.strftime('%Y%m%d%H%M%S')}"

                    interval = log_input.interval or 1
                    count = log_input.count or 1

                    # Parse datetime if provided
                    if log_input.datetime_iso:
                        datetime_obj = datetime.datetime.strptime(log_input.datetime_iso, "%Y-%m-%d %H:%M:%S")
                    else:
                        datetime_obj = None

                    # Obtain vendor from log_input
                    vendor = log_input.vendor or "Phantom"

                    # Initialize observables
                    observables_init = Observables()
                    observables = log_input.observables_dict
                    if observables:
                        observables_data = {}
                        for key, value in observables.__dict__.items():
                            if value is not None and key in observables_init.__dict__:
                                observables_data[key] = value
                        observables_obj = Observables(**observables_data)
                    else:
                        observables_obj = None

                    # Prepare required fields
                    required_fields = ",".join([field.value for field in log_input.required_fields]) if log_input.required_fields else ""

                    logger.info(f"Creating worker for type={log_input.type.name}, count={count}, destination={request_input.destination}")
                    logger.info(f"Observables: {observables_obj}, Required Fields: {required_fields}")
                    
                    # Create a worker for this log input
                    if request_input.destination == "XSIAM_WEBHOOK":
                        # v0.17.x store-driven: prefer the MCP-resolved
                        # xsiam_http endpoint + key; fall back to env defaults.
                        webhook_endpoint = request_input.webhook_url or WEBHOOK_ENDPOINT
                        if not webhook_endpoint:
                            raise ValueError(
                                "A webhook endpoint is required for XSIAM_WEBHOOK destination "
                                "(set WEBHOOK_ENDPOINT, or supply a store xsiam_http destination)."
                            )
                        headers = _get_webhook_headers(request_input.webhook_key)
                        data = _generate_worker_data(
                            log_input.type,
                            count,
                            datetime_obj,
                            observables_obj,
                            vendor,
                            log_input.product,
                            log_input.version,
                            required_fields,
                            log_input.fields,
                        )
                        event_type = f"phantom_{log_input.type.name.lower()}"
                        payloads = _build_webhook_payloads(data, event_type=event_type)
                        scenario_worker = WebhookSender(
                            worker_name=worker_name,
                            destination=webhook_endpoint,
                            payloads=payloads,
                            interval=interval,
                            verify_ssl=log_input.verify_ssl,
                            headers=headers,
                        )
                    else:
                        scenario_worker = Sender(
                            worker_name=worker_name,
                            data_type=log_input.type.name,
                            count=count,
                            destination=request_input.destination,
                            vendor=vendor,
                            product=log_input.product,
                            version=log_input.version,
                            observables=observables_obj,
                            interval=interval,
                            datetime_obj=datetime_obj,
                            required_fields=required_fields,
                            fields=log_input.fields
                        )

                    # Store and start the worker
                    workers[worker_name] = scenario_worker
                    scenario_worker.start()

                    # Collect output information
                    scenario_workers_output.append(
                        WorkerOutput(
                            type=scenario_worker.data_type,
                            worker=scenario_worker.worker_name,
                            status=scenario_worker.status,
                            count=scenario_worker.count,
                            interval=scenario_worker.interval,
                            destination=scenario_worker.destination,
                            verifySsl=str(scenario_worker.verify_ssl),
                            createdAt=str(scenario_worker.created_at)
                        )
                    )
        else:
            raise ValueError("No scenario steps provided in the request input.")

        if scenario_workers_output:
            first_step = scenario_steps[0] if scenario_steps else None
            _record_simulation_run(
                name=request_input.name,
                kind="scenario",
                destination=request_input.destination,
                worker_ids=[item.worker for item in scenario_workers_output],
                tags=request_input.tags,
                tactic=getattr(first_step, "tactic", None),
                technique=getattr(first_step, "technique_id", None) or getattr(first_step, "technique", None),
                procedure=getattr(first_step, "procedure", None),
                metadata={
                    "source": "scenario_query",
                    "steps": len(scenario_steps),
                },
            )
            try:
                store.create_scenario_package(
                    name=request_input.name,
                    status="active",
                    tags=request_input.tags,
                    attack={
                        "tactic": getattr(first_step, "tactic", None),
                        "technique": getattr(first_step, "technique_id", None) or getattr(first_step, "technique", None),
                        "procedure": getattr(first_step, "procedure", None),
                    },
                    telemetry={"worker_ids": [item.worker for item in scenario_workers_output]},
                    validation={},
                    metadata={"source": "scenario_query"},
                )
            except Exception as exc:
                logger.warning("Failed to persist scenario package: %s", exc)

        return scenario_workers_output

    @strawberry.field(description="Get a list of data workers.")
    def list_workers(self) -> List[WorkerOutput]:
        """
        Get a list of active data workers.

        Returns:
            List[DataWorkerOutput]: List of data worker objects containing information about each worker.

        """
        workers_data = []
        for worker in workers.keys():
            workers_data.append(WorkerOutput(type=workers[worker].data_type, worker=workers[worker].worker_name,
                                             status=workers[worker].status, count=workers[worker].count,
                                             interval=workers[worker].interval,
                                             verifySsl=workers[worker].verify_ssl,
                                             destination=workers[worker].destination,
                                             createdAt=str(workers[worker].created_at)))
        return workers_data

    @strawberry.field(description="Perform an action on a data worker.")
    def action_worker(self, request_input: DataWorkerActionInput) -> WorkerStatusOutput:
        """
        Perform an action on a data worker, such as stopping it.

        Args:
            request_input: Input object containing the worker ID and the action to perform.

        Returns:
            WorkerStatusOutput: Output object containing the worker ID and the status after the action.

        """
        if workers.get(request_input.worker):
            if request_input.action == WorkerActionEnum.STOP:
                workers[request_input.worker].stop()
                workers.pop(request_input.worker)
                return WorkerStatusOutput(worker=request_input.worker,
                                              status='Stopped')
            return WorkerStatusOutput(worker=workers[request_input.worker].worker_name,
                                          status=workers[request_input.worker].status)
        return WorkerStatusOutput(worker=request_input.worker, status="Worker not found.")

    @strawberry.field(description="Generate observables from threat intelligence feeds.")
    def generate_observables(self, request_input: GenerateObservablesInput) -> GenerateObservablesOutput:
        """
        Generate observables (IPs, URLs, hashes, CVEs, terms) from threat intelligence feeds.

        This leverages rosetta-ce's Observables.generator() to fetch real indicators from
        curated threat intel sources. If sources are unavailable, it falls back to generating
        realistic fake values.

        Args:
            request_input: Input object containing count, observable type, and known status (BAD/GOOD).

        Returns:
            GenerateObservablesOutput: Output object containing the generated observables.
        """
        from rosetta.rfaker import ObservableType, ObservableKnown

        # Map GraphQL enums to rosetta-ce enums
        type_mapping = {
            ObservableTypeEnum.IP: ObservableType.IP,
            ObservableTypeEnum.URL: ObservableType.URL,
            ObservableTypeEnum.SHA256: ObservableType.SHA256,
            ObservableTypeEnum.CVE: ObservableType.CVE,
            ObservableTypeEnum.TERMS: ObservableType.TERMS,
        }

        known_mapping = {
            ObservableKnownEnum.BAD: ObservableKnown.BAD,
            ObservableKnownEnum.GOOD: ObservableKnown.GOOD,
        }

        observable_type = type_mapping[request_input.observable_type]
        known = known_mapping[request_input.known] if request_input.known else ObservableKnown.BAD

        # Generate observables using rosetta-ce
        observables = Observables.generator(
            count=request_input.count,
            observable_type=observable_type,
            known=known
        )

        logger.info(f"Generated {len(observables)} {request_input.observable_type.value} observables (known={request_input.known.value if request_input.known else 'bad'})")

        return GenerateObservablesOutput(
            observables=observables,
            observable_type=request_input.observable_type.value,
            known=request_input.known.value if request_input.known else "bad",
            count=len(observables)
        )

    # ─── Technology Stack — read ────────────────────────────────
    #
    # The write side (updateTechnologyStack) lives on the Mutation
    # root below — Strawberry rejects `mutation { ... }` calls when
    # there's no Mutation type registered, so state-changing ops
    # need to be on a real Mutation class even though the rest of
    # this schema historically put "mutating" ops on Query as fields.
    # Reads stay here on Query.

    @strawberry.field(
        description=(
            "Return the org's current technology stack (vendor catalog "
            "+ default log destination). Reads from xlog's sqlite store "
            "first, falls back to the TECHNOLOGY_STACK env var, then to "
            "an empty stack with `configured: false`."
        )
    )
    def technology_stack(self) -> TechnologyStack:
        return stack_dict_to_type(store.get_technology_stack())


# ─── Mutation root ─────────────────────────────────────────────────
#
# Added when `updateTechnologyStack` was introduced. Other state-
# changing operations in this schema (create_data_worker, …) live on
# Query for legacy reasons and are called via the GraphQL `query`
# keyword; they should eventually migrate here. Until then, this
# root only holds the new tech-stack mutation, which is what makes
# a proper `mutation { ... }` call valid for the first time in this
# service.


@strawberry.type(description="Root mutation type.")
class Mutation:

    @strawberry.field(
        description=(
            "Replace the org's technology stack with the given payload. "
            "Full overwrite — `vendors` replaces the entire list (callers "
            "must include every vendor they want to keep). Idempotent and "
            "survives xlog restarts."
        )
    )
    def update_technology_stack(
        self, stack: TechnologyStackInput
    ) -> TechnologyStack:
        new_state = store.update_technology_stack(input_to_dict(stack))
        logger.info(
            "Technology stack updated: name=%s vendors=%d source=%s",
            new_state.get("stack_name"),
            new_state.get("total_vendors"),
            new_state.get("source"),
        )
        return stack_dict_to_type(new_state)


schema = strawberry.Schema(query=Query, mutation=Mutation)
