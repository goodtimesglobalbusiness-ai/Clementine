"""Stripe wrapper for premium subscriptions.

Thin helpers around Stripe Checkout, the Billing Portal, and webhook signature
verification. The guild_id is carried in metadata so the webhook knows which
server a subscription belongs to.
"""
from tts import config

try:
    import stripe
except ImportError:  # not installed in dev environments without billing
    stripe = None


def _ensure() -> None:
    if stripe is None:
        raise RuntimeError("the `stripe` package is not installed")
    if not config.STRIPE_API_KEY:
        raise RuntimeError("STRIPE_API_KEY is not set")
    stripe.api_key = config.STRIPE_API_KEY


def create_checkout_session(guild_id: int, price_id: str):
    """A subscription Checkout Session tagged with the guild it upgrades."""
    _ensure()
    gid = str(guild_id)
    return stripe.checkout.Session.create(
        mode="subscription",
        line_items=[{"price": price_id, "quantity": 1}],
        client_reference_id=gid,
        metadata={"guild_id": gid},
        # Mirror guild_id onto the subscription so later events carry it too.
        subscription_data={"metadata": {"guild_id": gid}},
        success_url=config.STRIPE_SUCCESS_URL,
        cancel_url=config.STRIPE_CANCEL_URL,
    )


def create_portal_session(customer_id: str):
    """A self-serve Billing Portal session for an existing customer."""
    _ensure()
    return stripe.billing_portal.Session.create(
        customer=customer_id, return_url=config.STRIPE_SUCCESS_URL
    )


def construct_event(payload: bytes, sig_header: str):
    """Verify and parse a Stripe webhook payload (raises on bad signature)."""
    _ensure()
    return stripe.Webhook.construct_event(
        payload, sig_header, config.STRIPE_WEBHOOK_SECRET
    )
