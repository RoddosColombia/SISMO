"""Router package — all API routers for RODDOS Contable IA."""
from . import auth, settings, alegra, chat, inventory, taxes, budget, dashboard, audit
from . import repuestos, loanbook, cartera

__all__ = [
    "auth", "settings", "alegra", "chat", "inventory", "taxes", "budget", "dashboard", "audit",
    "repuestos", "loanbook", "cartera",
]
