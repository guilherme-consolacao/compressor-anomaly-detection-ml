import argparse
import json
import logging
import signal
from pathlib import Path
from threading import Event

from .config import Settings
from .database import Repository, create_engine_for_url, inspect_contract
from .demo import run_demo
from .domain import MLBackendError, PersistenceError
from .services import MLService


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Measurement-level compressor ML backend")
    commands = parser.add_subparsers(dest="command", required=True)
    origin = commands.add_parser(
        "validate-public-data", help="Validate public development ancestry"
    )
    origin.add_argument("--manifest", type=Path, required=True)
    origin.add_argument("--sources", type=Path, default=Path("config/dataset-sources.json"))
    cycles = commands.add_parser(
        "predict-cycles", help="Research cycle candidate; requires confirmed boundaries and history"
    )
    cycles.add_argument("--manifest", type=Path, required=True)
    cycles.add_argument("--cycles", type=Path, required=True)
    readings = commands.add_parser(
        "predict-readings", help="Group readings by time gaps and score them as an experiment"
    )
    readings.add_argument("--manifest", type=Path, required=True)
    readings.add_argument("--readings", type=Path, required=True)
    readings.add_argument("--gap-seconds", type=int, required=True)
    commands.add_parser("check-db", help="Read-only connection and schema diagnostics")
    commands.add_parser("inspect-contract", help="Read-only acquisition compatibility report")
    extract = commands.add_parser("extract", help="Validate and persist one feature vector")
    extract.add_argument("measurement_id")
    dataset = commands.add_parser("prepare-data", help="Export labeled measurements to a new CSV")
    dataset.add_argument("--output", type=Path, required=True)
    train = commands.add_parser("train", help="Train and register a new immutable model version")
    train.add_argument("--version", required=True)
    evaluate = commands.add_parser("evaluate", help="Replay the original holdout evaluation")
    evaluate.add_argument("--model-id", type=int, required=True)
    commands.add_parser("models", help="List registered model versions and metrics")
    details = commands.add_parser("model", help="Inspect metadata without loading an artifact")
    details.add_argument("model_id", type=int)
    predict = commands.add_parser("predict", help="Predict an explicitly finalized measurement")
    predict.add_argument("measurement_id")
    predict.add_argument("--model-id", type=int, required=True)
    pending = commands.add_parser(
        "process-pending", help="Process finalized, unpredicted measurements"
    )
    pending.add_argument("--model-id", type=int, required=True)
    pending.add_argument("--limit", type=int, default=100)
    watch = commands.add_parser("watch", help="Poll with bounded batches; stop with Ctrl+C")
    watch.add_argument("--model-id", type=int, required=True)
    watch.add_argument("--limit", type=int, default=100)
    predictions = commands.add_parser("predictions", help="List persisted predictions")
    predictions.add_argument("--limit", type=int, default=100)
    demo = commands.add_parser("demo", help="Create a new isolated SQLite synthetic demonstration")
    demo.add_argument("--database", type=Path, default=Path("demo.sqlite"))
    return parser


def _print(value: object) -> None:
    print(json.dumps(value, indent=2, ensure_ascii=False, allow_nan=False))


def _watch(service: MLService, model_id: int, limit: int, interval: float) -> None:
    stopped = Event()
    previous = {}
    for signum in (signal.SIGINT, signal.SIGTERM):
        previous[signum] = signal.signal(signum, lambda *_args: stopped.set())
    try:
        while not stopped.is_set():
            try:
                _print(service.process_pending(model_id, limit))
            except PersistenceError:
                logging.getLogger(__name__).warning("Database temporarily unavailable; retrying.")
            stopped.wait(interval)
    finally:
        for signum, handler in previous.items():
            signal.signal(signum, handler)


def main(argv: list[str] | None = None) -> int:
    parser = _parser()
    args = parser.parse_args(argv)
    if hasattr(args, "limit") and not 1 <= args.limit <= 10000:
        parser.error("--limit must be between 1 and 10000")
    engine = None
    try:
        if args.command == "validate-public-data":
            from .provenance import validate_public_file

            _print(validate_public_file(args.manifest, args.sources))
            return 0
        if args.command == "demo":
            _print(run_demo(args.database))
            return 0
        if args.command == "predict-readings":
            from .cycle_candidate import load_cycle_candidate
            from .reading_measurements import predict_reading_measurements

            artifact, manifest = load_cycle_candidate(args.manifest, Path("models"))
            _print(
                {
                    "model_version": manifest["version"],
                    "grouping_rule": "time-gap-v1",
                    "gap_seconds": args.gap_seconds,
                    "scope": "exploratory telemetry grouping; no field validation",
                    "measurements": predict_reading_measurements(
                        artifact,
                        json.loads(args.readings.read_text(encoding="utf-8-sig")),
                        gap_seconds=args.gap_seconds,
                    ),
                }
            )
            return 0
        settings = Settings.from_env()
        if args.command == "predict-cycles":
            from .cycle_candidate import load_cycle_candidate, predict_completed_cycles

            artifact, manifest = load_cycle_candidate(args.manifest, settings.model_dir)
            _print(
                {
                    "model_version": manifest["version"],
                    "contract_version": manifest["contract_version"],
                    "local_portability_status": manifest["local_portability_status"],
                    "predictions": predict_completed_cycles(
                        artifact, json.loads(args.cycles.read_text(encoding="utf-8"))
                    ),
                }
            )
            return 0
        logging.basicConfig(
            level=settings.log_level, format="%(asctime)s %(levelname)s %(name)s %(message)s"
        )
        engine = create_engine_for_url(settings.database_url)
        if args.command in {"check-db", "inspect-contract"}:
            report = inspect_contract(engine)
            _print(report)
            return 0 if report["measurement_contract_available"] else 2
        service = MLService(Repository(engine), settings.model_dir)
        match args.command:
            case "extract":
                result = service.extract(args.measurement_id)
            case "prepare-data":
                result = service.export_dataset(args.output)
            case "train":
                result = service.train(args.version, settings.training)
            case "evaluate":
                result = service.evaluate_model(args.model_id)
            case "models":
                result = service.repository.list_models()
            case "model":
                result = service.model_details(args.model_id)
            case "predict":
                result = service.predict(args.measurement_id, args.model_id)
            case "process-pending":
                result = service.process_pending(args.model_id, args.limit)
            case "predictions":
                result = service.repository.list_predictions(args.limit)
            case "watch":
                _watch(service, args.model_id, args.limit, settings.poll_interval_seconds)
                return 0
        _print(result)
        return 2 if isinstance(result, dict) and result.get("errors") else 0
    except MLBackendError as exc:
        _print({"error": type(exc).__name__, "message": str(exc)})
        return 1
    except (OSError, ValueError):
        _print(
            {"error": "LocalIOError", "message": "Local file operation or configuration failed."}
        )
        return 1
    finally:
        if engine is not None:
            engine.dispose()


if __name__ == "__main__":
    raise SystemExit(main())
