from fastapi import FastAPI


app = FastAPI(title="kokkai")


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
