
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from .settings import settings

app = FastAPI()

# CORS for frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.frontend_cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Static files (optional, if needed for frontend)
app.mount("/static", StaticFiles(directory="static"), name="static")

# --- Schemas ---
class PublicLeadCaptureInput(BaseModel):
    email: str
    source: str
    preocupacion_negociacion: str = ""

class PublicLeadCaptureResponse(BaseModel):
    ok: bool
    message: str

class SolicitorAsesoriaInput(BaseModel):
    email: str
    nombre: str
    tamaño_equipo: str
    preocupacion: str

class Protocolo48hInput(BaseModel):
    email: str

class PDFDownloadInput(BaseModel):
    email: str
    name: str
    pdf_name: str

# --- Endpoints ---
@app.get("/api/health")
def health_check():
    return {"status": "ok", "message": "API is running"}

@app.post("/api/public/leads/contact", response_model=PublicLeadCaptureResponse)
def capture_public_lead(payload: PublicLeadCaptureInput):
    email = payload.email.strip().lower()
    try:
        from .brevo_engine import upsert_contact_in_brevo
        upsert_contact_in_brevo(
            email,
            payload.preocupacion_negociacion.strip(),
            payload.source
        )
    except RuntimeError as exc:
        raise HTTPException(status_code=502, detail=f"No se pudo enviar el lead a Brevo: {exc}")
    return PublicLeadCaptureResponse(
        ok=True,
        message="Protocolo de contacto iniciado. Recibirá un correo con los próximos pasos",
    )

@app.post("/api/public/solicitar-asesoria", response_model=PublicLeadCaptureResponse)
def solicitar_asesoria(payload: SolicitorAsesoriaInput):
    email = payload.email.strip().lower()
    try:
        from .brevo_engine import upsert_contact_in_brevo
        upsert_contact_in_brevo(
            email,
            f"Asesoría solicitada - Equipo: {payload.tamaño_equipo} - {payload.preocupacion}",
            "solicitar_asesoria"
        )
    except RuntimeError as exc:
        print(f"⚠️ No se pudo enviar solicitud de asesoría a Brevo ({email}): {exc}")
    return PublicLeadCaptureResponse(
        ok=True,
        message="Solicitud de asesoría registrada. Te contactaremos pronto con los próximos pasos",
    )

@app.post("/api/public/protocolo-48h", response_model=PublicLeadCaptureResponse)
def protocolo_48h(payload: Protocolo48hInput):
    email = payload.email.strip().lower()
    try:
        from .brevo_engine import upsert_contact_in_brevo
        upsert_contact_in_brevo(
            email,
            "Interés en sesión de asesoramiento en 48 horas",
            "protocolo_48h"
        )
    except RuntimeError as exc:
        print(f"⚠️ No se pudo enviar lead de asesoramiento 48h a Brevo ({email}): {exc}")
    return PublicLeadCaptureResponse(
        ok=True,
        message="Solicitud recibida. En breve nos comunicaremos para agendar su sesión de asesoramiento.",
    )

@app.post("/api/public/pdf-download", response_model=PublicLeadCaptureResponse)
def pdf_download(payload: PDFDownloadInput):
    email = payload.email.strip().lower()
    name = payload.name.strip()
    pdf_name = payload.pdf_name.strip()
    pdf_urls = {
        "si_te_calentas_perdes": "https://rodrigoborgia.com/pdfs/si-te-calentas-perdes.pdf",
    }
    pdf_url = pdf_urls.get(pdf_name)
    if not pdf_url:
        raise HTTPException(status_code=404, detail="PDF no encontrado")
    try:
        from .brevo_engine import send_pdf_email, upsert_contact_in_brevo
        send_pdf_email(
            user_email=email,
            user_name=name,
            pdf_name=pdf_name,
            pdf_url=pdf_url
        )
        upsert_contact_in_brevo(
            email,
            f"Lead Magnet: {pdf_name}",
            "pdf_download"
        )
    except RuntimeError as exc:
        print(f"⚠️ No se pudo enviar PDF por email ({email}): {exc}")
    return PublicLeadCaptureResponse(
        ok=True,
        message="PDF enviado a tu email. Revisá tu bandeja de entrada.",
    )


def _utc_now() -> datetime:
    return datetime.now(UTC)





app = FastAPI(title="RB Strategic Framework API", lifespan=lifespan)

# Montar carpeta de videos como archivos estáticos
app.mount("/static/videos", StaticFiles(directory="app/static/videos"), name="videos")

# ===== MIDDLEWARE: Redirecciones HTTPS y sin WWW =====
@app.middleware("http")
async def redirect_https_and_www(request: Request, call_next):
    """
    Middleware para redirigir:
    - http:// → https://
    - www.rodrigoborgia.com → rodrigoborgia.com
    Usa código 301 (Moved Permanently) para SEO
    
    Excluye: localhost, 127.0.0.1, testserver (testing)
    """
    scheme = request.url.scheme
    host = request.url.netloc
    hostname = (request.url.hostname or "").lower()
    path = request.url.path
    query = request.url.query

    # Aplicar redirecciones solo para dominios productivos
    production_hosts = {"rodrigoborgia.com", "www.rodrigoborgia.com"}
    if hostname not in production_hosts:
        return await call_next(request)

    # Construir URL destino normalizada
    target_host = host.lower()
    
    # Remover www
    if target_host.startswith("www."):
        target_host = target_host.replace("www.", "", 1)
    
    # Construir URL final (siempre HTTPS)
    should_redirect = False
    target_url = None

    # Si es http, redirigir a https (solo en producción)
    if scheme == "http":
        should_redirect = True
    
    # Si contiene www, redirigir sin www
    if host.lower().startswith("www."):
        should_redirect = True

    if should_redirect:
        target_url = f"https://{target_host}{path}"
        if query:
            target_url += f"?{query}"
        return RedirectResponse(url=target_url, status_code=301)

    # Continuar con el siguiente middleware/handler
    return await call_next(request)
# ===== FIN MIDDLEWARE =====

app.add_middleware(
    CORSMiddleware,
    allow_origins=list(settings.frontend_origins),
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    # Log the error details
    error_msg = f"Error en {request.method} {request.url.path}: {str(exc)}"
    print(f"❌ {error_msg}")
    print(f"Stack trace: {traceback.format_exc()}")
    
    return JSONResponse(
        status_code=500,
        content={
            "detail": "Internal Server Error",
            "error": str(exc),
            "path": request.url.path,
        }
    )








def _is_valid_period_label(value: str) -> bool:
    if len(value) != 7:
        return False
    try:
        datetime.strptime(f"{value}-01", "%Y-%m-%d")
        return True
    except ValueError:
        return False

@app.get("/api/health")
def health_check() -> dict:
    return {"ok": True}

# ============== HEALTH CHECK & DIAGNOSTICS ==============

@app.get("/api/health")
def health_check() -> dict:
    """Simple health check endpoint"""
    return {"status": "ok", "message": "API is running"}


@app.post("/api/public/leads/contact", response_model=PublicLeadCaptureResponse)
def capture_public_lead(
    payload: PublicLeadCaptureInput,
    session: Session = Depends(get_session)
) -> PublicLeadCaptureResponse:
    email = payload.email.strip().lower()
    
    # Sync to Brevo
    try:
        from .brevo_engine import upsert_contact_in_brevo

        upsert_contact_in_brevo(
            email, 
            payload.preocupacion_negociacion.strip(),
            payload.source
        )
    except RuntimeError as exc:
        raise HTTPException(status_code=502, detail=f"No se pudo enviar el lead a Brevo: {exc}")

    return PublicLeadCaptureResponse(
        ok=True,
        message="Protocolo de contacto iniciado. Recibirá un correo con los próximos pasos",
    )




@app.post("/api/public/solicitar-asesoria", response_model=PublicLeadCaptureResponse)
def solicitar_asesoria(
    payload: SolicitorAsesoriaInput,
    session: Session = Depends(get_session)
) -> PublicLeadCaptureResponse:
    """Solicitud de asesoría directa: Nombre, email, tamaño equipo, preocupación"""
    email = payload.email.strip().lower()
    
    # Sync to Brevo
    try:
        from .brevo_engine import upsert_contact_in_brevo
        
        upsert_contact_in_brevo(
            email,
            f"Asesoría solicitada - Equipo: {payload.tamaño_equipo} - {payload.preocupacion}",
            "solicitar_asesoria"
        )
    except RuntimeError as exc:
        # Log but don't fail - graceful degradation
        print(f"⚠️ No se pudo enviar solicitud de asesoría a Brevo ({email}): {exc}")
    
    return PublicLeadCaptureResponse(
        ok=True,
        message="Solicitud de asesoría registrada. Te contactaremos pronto con los próximos pasos",
    )


@app.post("/api/public/protocolo-48h", response_model=PublicLeadCaptureResponse)
def protocolo_48h(
    payload: Protocolo48hInput,
    session: Session = Depends(get_session)
) -> PublicLeadCaptureResponse:
    """Protocolo 48 Horas lead capture"""
    email = payload.email.strip().lower()

    # Sync to Brevo
    try:
        from .brevo_engine import upsert_contact_in_brevo

        upsert_contact_in_brevo(
            email,
            "Interés en sesión de asesoramiento en 48 horas",
            "protocolo_48h"
        )
    except RuntimeError as exc:
        # Log but don't fail - graceful degradation
        print(f"⚠️ No se pudo enviar lead de asesoramiento 48h a Brevo ({email}): {exc}")

    return PublicLeadCaptureResponse(
        ok=True,
        message="Solicitud recibida. En breve nos comunicaremos para agendar su sesión de asesoramiento.",
    )


@app.post("/api/public/pdf-download", response_model=PublicLeadCaptureResponse)
def pdf_download(
    payload: PDFDownloadInput,
    session: Session = Depends(get_session)
) -> PublicLeadCaptureResponse:
    """PDF download and lead capture - sends PDF via email"""
    email = payload.email.strip().lower()
    name = payload.name.strip()
    pdf_name = payload.pdf_name.strip()

    # Map PDF names to actual files/URLs
    pdf_urls = {
        "si_te_calentas_perdes": "https://rodrigoborgia.com/pdfs/si-te-calentas-perdes.pdf",
        # Add more PDFs as needed
    }

    pdf_url = pdf_urls.get(pdf_name)
    if not pdf_url:
        raise HTTPException(status_code=404, detail="PDF no encontrado")

    # Send PDF via email
    try:
        from .brevo_engine import send_pdf_email, upsert_contact_in_brevo

        # Send the PDF email
        send_pdf_email(
            user_email=email,
            user_name=name,
            pdf_name=pdf_name,
            pdf_url=pdf_url
        )

        # Add to Brevo contact list
        upsert_contact_in_brevo(
            email,
            f"Lead Magnet: {pdf_name}",
            "pdf_download"
        )
    except RuntimeError as exc:
        # Log but don't fail - graceful degradation
        print(f"⚠️ No se pudo enviar PDF por email ({email}): {exc}")

    return PublicLeadCaptureResponse(
        ok=True,
        message="PDF enviado a tu email. Revisá tu bandeja de entrada.",
    )

@app.exception_handler(Exception)
async def generic_exception_handler(request: Request, exc: Exception):
    # Log the traceback for debugging
    tb = traceback.format_exc()
    print(f"Internal Server Error: {tb}")
    return JSONResponse(
        status_code=500,
        content={
            "detail": "Internal Server Error",
            "error": str(exc),
            "traceback": tb,
        },
    )

@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    return JSONResponse(
        status_code=422,
        content={"detail": exc.errors(), "body": exc.body},
    )
