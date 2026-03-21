from __future__ import annotations

import logging

from .settings import settings

logger = logging.getLogger(__name__)


def upsert_contact_in_brevo(email: str, concern: str, source: str = "modal") -> None:
    if not settings.brevo_api_key:
        raise RuntimeError("BREVO_API_KEY no configurada")

    try:
        import sib_api_v3_sdk
        from sib_api_v3_sdk.rest import ApiException
    except ImportError as exc:
        raise RuntimeError("Dependencia sib_api_v3_sdk no instalada") from exc

    configuration = sib_api_v3_sdk.Configuration()
    configuration.api_key["api-key"] = settings.brevo_api_key

    api_client = sib_api_v3_sdk.ApiClient(configuration)
    contacts_api = sib_api_v3_sdk.ContactsApi(api_client)

    source_labels = {
        "lead_magnet": "Lead Magnet: Protocolo IA",
        "modal": "Lead Magnet: Asesoría Equipos",
        "demo": "Demo: Exploración Framework",
        "solicitar_asesoria": "Solicitud: Asesoría Directa",
        "protocolo_48h": "Solicitud: Asesoramiento 48h",
    }
    source_label = source_labels.get(source, "Lead Magnet: Asesoría Equipos")

    attributes = {
        settings.brevo_interest_attribute: concern,
        settings.brevo_source_attribute: source_label,
    }

    payload = sib_api_v3_sdk.CreateContact(
        email=email,
        list_ids=[settings.brevo_list_id],
        update_enabled=True,
        attributes=attributes,
    )

    try:
        result = contacts_api.create_contact(payload)
        logger.info(
            f"Lead capturado exitosamente: email={email}, source={source_label}, list_id={settings.brevo_list_id}"
        )
    except ApiException as exc:
        logger.error(f"Brevo API error para {email}: {exc}")
        raise RuntimeError(f"Brevo API error: {exc}") from exc




def send_case_closure_email(
    user_email: str,
    case_title: str,
    final_memo: dict,
) -> None:
    """Send case closure summary email to user via Brevo"""
    if not settings.brevo_api_key:
        logger.warning("BREVO_API_KEY no configurada, no se envió email de cierre de caso")
        return

    try:
        import sib_api_v3_sdk
        from sib_api_v3_sdk.rest import ApiException
    except ImportError as exc:
        logger.error(f"Dependencia sib_api_v3_sdk no instalada: {exc}")
        return

    configuration = sib_api_v3_sdk.Configuration()
    configuration.api_key["api-key"] = settings.brevo_api_key

    api_client = sib_api_v3_sdk.ApiClient(configuration)
    transactional_api = sib_api_v3_sdk.TransactionalEmailsApi(api_client)

    # Extract memo fields
    strategic_synthesis = final_memo.get("strategic_synthesis", "")
    observations = final_memo.get("observations_and_next_steps", [])
    inconsistencies = final_memo.get("open_inconsistencies", [])
    thinking_pattern = final_memo.get("observed_thinking_pattern", "")
    transferable_principle = final_memo.get("consolidated_transferable_principle", "")

    # Build HTML email body with landing page aesthetic
    html_body = f"""
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
</head>
<body style="margin: 0; padding: 0; background: #0f1419; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;">
    <div style="max-width: 600px; margin: 0 auto; padding: 40px 20px;">
        <!-- Header -->
        <div style="text-align: center; margin-bottom: 32px;">
            <h1 style="color: #60a5fa; font-size: 24px; margin: 0 0 8px 0;">✅ Caso Cerrado</h1>
            <h2 style="color: #e5e7eb; font-size: 18px; margin: 0; font-weight: 600;">{case_title}</h2>
        </div>
<html>
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
</head>
<body style="margin: 0; padding: 0; background: #0f1419; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', 'Open Sans', sans-serif;">
    <div style="max-width: 600px; margin: 0 auto; padding: 40px 20px;">
        
        <!-- Header -->
        <div style="text-align: center; margin-bottom: 32px;">
            <h1 style="color: #ffffff; font-size: 28px; margin: 0 0 8px 0; font-weight: 900;">
                {metadata["title"]}
            </h1>
            <p style="color: #94a3b8; font-size: 14px; margin: 0;">
                Tu documento está listo
            </p>
        </div>

        <!-- Main Container -->
        <div style="background: #111111; border: 1px solid #262626; border-radius: 14px; padding: 32px; margin-bottom: 24px;">
            
            <p style="color: #e5e7eb; font-size: 16px; line-height: 1.6; margin: 0 0 20px 0;">
                Hola {user_name},
            </p>

            <p style="color: #cbd5e1; font-size: 15px; line-height: 1.65; margin: 0 0 20px 0;">
                {metadata["description"]}
            </p>

            <!-- Download Button -->
            <div style="text-align: center; margin: 32px 0;">
                <a href="{pdf_url or '#'}" 
                   style="display: inline-block; background: #3b82f6; color: #ffffff; font-size: 16px; font-weight: 700; padding: 16px 32px; border-radius: 14px; text-decoration: none;">
                    📄 Descargar PDF
                </a>
            </div>

            <div style="background: rgba(96, 165, 250, 0.05); border-left: 3px solid #60a5fa; padding: 16px; border-radius: 8px; margin: 24px 0 0 0;">
                <p style="color: #bfdbfe; font-size: 14px; line-height: 1.6; margin: 0; font-style: italic;">
                    {metadata["cta_text"]}
                </p>
            </div>
        </div>

        <!-- CTA Section -->
        <div style="background: linear-gradient(135deg, #1e293b 0%, #0f1419 100%); border: 1px solid #475569; border-radius: 14px; padding: 28px; margin-bottom: 24px; text-align: center;">
            <h2 style="color: #ffffff; font-size: 20px; margin: 0 0 12px 0; font-weight: 700;">
                ¿Tenés una negociación importante por delante?
            </h2>
            <p style="color: #cbd5e1; font-size: 15px; line-height: 1.6; margin: 0 0 20px 0;">
                Si estás frente a una negociación compleja o querés preparar una conversación estratégica con tu equipo, podemos trabajarla juntos.
            </p>
            <a href="https://api.whatsapp.com/send?phone=5493416087362&text=Hola%20Rodrigo%2C%20acabo%20de%20descargar%20el%20PDF%20y%20me%20gustar%C3%ADa%20conversar%20sobre%20una%20negociaci%C3%B3n%20que%20tengo%20por%20delante." 
               style="display: inline-block; background: transparent; color: #60a5fa; border: 2px solid #60a5fa; font-size: 15px; font-weight: 700; padding: 12px 24px; border-radius: 14px; text-decoration: none;">
                💬 Agendar una conversación
            </a>
        </div>

        <!-- Footer -->
        <div style="text-align: center; padding-top: 20px; border-top: 1px solid #262626;">
            <p style="color: #64748b; font-size: 13px; line-height: 1.6; margin: 0;">
                RB Strategic Framework<br />
                <a href="https://rodrigoborgia.com" style="color: #60a5fa; text-decoration: none;">rodrigoborgia.com</a>
            </p>
        </div>
    </div>
</body>
</html>
"""

    sender = {
        "name": settings.brevo_sender_name,
        "email": settings.brevo_sender_email,
    }
    
    to = [{"email": user_email}]

    send_smtp_email = sib_api_v3_sdk.SendSmtpEmail(
        to=to,
        html_content=html_body,
        sender=sender,
        subject=f"📄 {metadata['title']} - Tu documento está listo",
    )

    try:
        response = transactional_api.send_transac_email(send_smtp_email)
        logger.info(f"PDF email enviado exitosamente a {user_email} para '{pdf_name}'")
    except ApiException as exc:
        logger.warning(f"No se pudo enviar PDF a {user_email}: {exc}")


