from fastapi import APIRouter

from omnidoc.api.schemas import ProviderOut, ProvidersOut
from omnidoc.core.config import get_settings
from omnidoc.providers.email.factory import configured_email_providers
from omnidoc.providers.llm.factory import configured_providers, provider_label

router = APIRouter(tags=["meta"])


@router.get("/providers", response_model=ProvidersOut)
def providers():
    """What a frontend can offer in its 'choose your AI' and 'choose your email service' pickers.
    Only names are returned, never keys. Public so it works on the login screen."""
    names = configured_providers()
    default = get_settings().default_llm
    return ProvidersOut(llm=[ProviderOut(name=n, label=provider_label(n)) for n in names],
                        default_llm=default if default in names else (
                            names[0] if names else None),
                        email=configured_email_providers())
