"""QualityCheck Flet + ruta privada de descargas HTTPS.
Ejecutar: uvicorn servidor_pdf:app --host 0.0.0.0 --port $PORT
"""
from contextlib import asynccontextmanager
import flet.fastapi as flet_fastapi
from fastapi import FastAPI, HTTPException
from fastapi.responses import Response
from login import main
from descarga_pdf_segura import retirar_descarga

@asynccontextmanager
async def lifespan(app: FastAPI):
    await flet_fastapi.app_manager.start()
    yield
    await flet_fastapi.app_manager.shutdown()

app = FastAPI(lifespan=lifespan)

@app.get('/qc-download/{ticket}')
def descargar(ticket: str):
    item = retirar_descarga(ticket)
    if item is None:
        raise HTTPException(status_code=404, detail='Descarga vencida o inexistente')
    contenido, nombre = item
    return Response(
        contenido,
        media_type='application/pdf',
        headers={
            'Content-Disposition': f'attachment; filename="{nombre}"',
            'Cache-Control': 'no-store, private',
            'X-Content-Type-Options': 'nosniff',
        },
    )

# Montar Flet al final para no ocultar /qc-download.
app.mount('/', flet_fastapi.app(main, assets_dir='assets'))
