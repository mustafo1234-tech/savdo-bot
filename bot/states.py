from __future__ import annotations

from aiogram.fsm.state import State, StatesGroup


class SellerStates(StatesGroup):
    platform = State()
    account_name = State()
    account_identifier = State()
    level = State()
    items = State()
    description = State()
    price = State()
    images = State()
    contact = State()
    payout = State()
    ownership = State()
    preview = State()
    edit_value = State()


class BuyerStates(StatesGroup):
    search = State()


class SupportStates(StatesGroup):
    message = State()


class ReviewStates(StatesGroup):
    comment = State()


class DisputeStates(StatesGroup):
    reason = State()
    evidence = State()


class AdminStates(StatesGroup):
    broadcast = State()
    set_value = State()
