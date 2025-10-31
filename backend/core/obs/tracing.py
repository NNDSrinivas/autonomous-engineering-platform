from __future__ import annotations
import os

OTEL_ENABLED = os.getenv("OTEL_ENABLED", "true").lower() == "true"


def init_tracing() -> None:
    if not OTEL_ENABLED:
        return
    # Lightweight init; uses OTLP/gRPC or HTTP per env
    # pip deps: opentelemetry-sdk, opentelemetry-exporter-otlp, opentelemetry-instrumentation-fastapi
    try:
        from opentelemetry import trace

        try:
            from opentelemetry.exporter.otlp.proto.http.trace_exporter import (
                OTLPSpanExporter as OTLPHTTP,
            )
        except ImportError:
            # Fallback to different import path if needed
            return

        from opentelemetry.sdk.resources import Resource
        from opentelemetry.sdk.trace import TracerProvider
        from opentelemetry.sdk.trace.export import BatchSpanProcessor
        from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor

        endpoint = os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT", "http://localhost:4318")
        service_name = os.getenv("APP_NAME", "aep")

        resource = Resource.create({"service.name": service_name})
        provider = TracerProvider(resource=resource)
        trace.set_tracer_provider(provider)

        exporter = OTLPHTTP(endpoint=f"{endpoint}/v1/traces")
        processor = BatchSpanProcessor(exporter)
        provider.add_span_processor(processor)

        # FastAPI instrumentation will be attached in api.main after app is created
        FastAPIInstrumentor().instrument()  # fixed: call instrument method properly
    except Exception:
        # If Otel deps are absent, skip silently (env-driven)
        pass
