from telegram import InlineKeyboardButton, InlineKeyboardMarkup

from backend.src.ai.prompts.assessment import (
    GOALS_OPTIONS,
    SELF_DECLARATION_OPTIONS,
    TARGET_COMPANY_OPTIONS,
    TARGET_STACK_OPTIONS,
    TECH_ROLE_OPTIONS,
    TECH_STACK_OPTIONS,
)


def build_self_declaration_keyboard() -> InlineKeyboardMarkup:
    buttons = [
        [InlineKeyboardButton(text=opt, callback_data=f"self_declaration:{opt.lower()}")]
        for opt in SELF_DECLARATION_OPTIONS
    ]
    return InlineKeyboardMarkup(buttons)


def build_tech_role_keyboard() -> InlineKeyboardMarkup:
    buttons = []
    row: list[InlineKeyboardButton] = []
    for opt in TECH_ROLE_OPTIONS:
        value = opt.lower().replace("/", "_")
        row.append(InlineKeyboardButton(text=opt, callback_data=f"tech_role:{value}"))
        if len(row) == 2:
            buttons.append(row)
            row = []
    if row:
        buttons.append(row)
    return InlineKeyboardMarkup(buttons)


def build_multi_select_keyboard(
    category: str,
    options: list[str],
    selected: set[str],
    show_other: bool = True,
) -> InlineKeyboardMarkup:
    # Include any custom selections not in predefined options
    all_options = list(options)
    for s in selected:
        if s not in all_options:
            all_options.append(s)

    buttons = []
    row: list[InlineKeyboardButton] = []
    for opt in all_options:
        prefix = "\u2713 " if opt in selected else ""
        row.append(
            InlineKeyboardButton(
                text=f"{prefix}{opt}",
                callback_data=f"toggle:{category}:{opt}",
            )
        )
        if len(row) == 2:
            buttons.append(row)
            row = []
    if row:
        buttons.append(row)

    buttons.append([
        InlineKeyboardButton(text="\u2705 Confirm", callback_data=f"confirm:{category}")
    ])
    return InlineKeyboardMarkup(buttons)


def build_goals_keyboard(selected: set[str]) -> InlineKeyboardMarkup:
    buttons = []
    for value, label in GOALS_OPTIONS:
        prefix = "\u2713 " if value in selected else ""
        buttons.append([
            InlineKeyboardButton(
                text=f"{prefix}{label}",
                callback_data=f"toggle:goals:{value}",
            )
        ])
    buttons.append([
        InlineKeyboardButton(text="\u2705 Confirm", callback_data="confirm:goals")
    ])
    return InlineKeyboardMarkup(buttons)


def build_target_stack_keyboard(selected: set[str]) -> InlineKeyboardMarkup:
    return build_multi_select_keyboard("target_stack", TARGET_STACK_OPTIONS, selected)


def build_tech_stack_keyboard(selected: set[str]) -> InlineKeyboardMarkup:
    return build_multi_select_keyboard("tech_stack", TECH_STACK_OPTIONS, selected)


def build_target_company_keyboard() -> InlineKeyboardMarkup:
    buttons = []
    row: list[InlineKeyboardButton] = []
    for opt in TARGET_COMPANY_OPTIONS:
        value = opt.lower().replace(" ", "_")
        row.append(InlineKeyboardButton(text=opt, callback_data=f"target_company:{value}"))
        if len(row) == 2:
            buttons.append(row)
            row = []
    if row:
        buttons.append(row)
    return InlineKeyboardMarkup(buttons)
