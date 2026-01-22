"""
Inline keyboard builders for AbaQuiz.

Creates Telegram inline keyboards for quiz answers, settings, etc.
"""

from typing import Optional

from telegram import InlineKeyboardButton, InlineKeyboardMarkup

from src.config.constants import COMMON_TIMEZONES, REGION_LABELS, TIMEZONE_REGIONS, ContentArea


def build_answer_keyboard(
    question_id: int,
    question_type: str,
    options: Optional[dict[str, str]] = None,
) -> InlineKeyboardMarkup:
    """
    Build answer keyboard for a question.

    Args:
        question_id: Question ID for callback data
        question_type: 'multiple_choice' or 'true_false'
        options: Answer options (for multiple choice)

    Returns:
        InlineKeyboardMarkup with answer buttons
    """
    if question_type == "true_false":
        buttons = [
            [
                InlineKeyboardButton(
                    "True",
                    callback_data=f"answer:{question_id}:True",
                ),
                InlineKeyboardButton(
                    "False",
                    callback_data=f"answer:{question_id}:False",
                ),
            ]
        ]
    else:
        # Multiple choice - one button per row for clarity
        buttons = []
        for key in ["A", "B", "C", "D"]:
            if options and key in options:
                # Truncate long options for button text
                option_text = options[key]
                if len(option_text) > 50:
                    option_text = option_text[:47] + "..."
                buttons.append(
                    [
                        InlineKeyboardButton(
                            f"{key}. {option_text}",
                            callback_data=f"answer:{question_id}:{key}",
                        )
                    ]
                )

    return InlineKeyboardMarkup(buttons)


def build_content_area_keyboard(
    prefix: str = "area",
    include_all: bool = True,
) -> InlineKeyboardMarkup:
    """
    Build keyboard for content area selection.

    Args:
        prefix: Callback data prefix
        include_all: Whether to include "All areas" option

    Returns:
        InlineKeyboardMarkup with content area buttons
    """
    buttons = []

    if include_all:
        buttons.append(
            [
                InlineKeyboardButton(
                    "🎲 Random (All areas)",
                    callback_data=f"{prefix}:random",
                )
            ]
        )

    # Group areas by section
    section_1 = [
        ContentArea.PHILOSOPHICAL_UNDERPINNINGS,
        ContentArea.CONCEPTS_AND_PRINCIPLES,
        ContentArea.MEASUREMENT,
        ContentArea.EXPERIMENTAL_DESIGN,
    ]

    section_2 = [
        ContentArea.ETHICS,
        ContentArea.BEHAVIOR_ASSESSMENT,
        ContentArea.BEHAVIOR_CHANGE_PROCEDURES,
        ContentArea.INTERVENTIONS,
        ContentArea.SUPERVISION,
    ]

    # Add Section 1 header
    buttons.append(
        [InlineKeyboardButton("── Section 1: Foundations ──", callback_data="noop")]
    )

    for area in section_1:
        # Use short display names
        display_name = _get_short_area_name(area)
        buttons.append(
            [
                InlineKeyboardButton(
                    display_name,
                    callback_data=f"{prefix}:{area.value}",
                )
            ]
        )

    # Add Section 2 header
    buttons.append(
        [InlineKeyboardButton("── Section 2: Applications ──", callback_data="noop")]
    )

    for area in section_2:
        display_name = _get_short_area_name(area)
        buttons.append(
            [
                InlineKeyboardButton(
                    display_name,
                    callback_data=f"{prefix}:{area.value}",
                )
            ]
        )

    return InlineKeyboardMarkup(buttons)


def _get_short_area_name(area: ContentArea) -> str:
    """Get shortened display name for content area."""
    short_names = {
        ContentArea.PHILOSOPHICAL_UNDERPINNINGS: "Philosophical Underpinnings",
        ContentArea.CONCEPTS_AND_PRINCIPLES: "Concepts & Principles",
        ContentArea.MEASUREMENT: "Measurement & Data",
        ContentArea.EXPERIMENTAL_DESIGN: "Experimental Design",
        ContentArea.ETHICS: "Ethics",
        ContentArea.BEHAVIOR_ASSESSMENT: "Behavior Assessment",
        ContentArea.BEHAVIOR_CHANGE_PROCEDURES: "Behavior-Change Procedures",
        ContentArea.INTERVENTIONS: "Interventions",
        ContentArea.SUPERVISION: "Supervision & Management",
    }
    return short_names.get(area, area.value)


def build_timezone_keyboard() -> InlineKeyboardMarkup:
    """
    Build keyboard for timezone selection (legacy flat list).

    Returns:
        InlineKeyboardMarkup with timezone buttons
    """
    buttons = []

    for tz_name, display_name in COMMON_TIMEZONES:
        buttons.append(
            [
                InlineKeyboardButton(
                    display_name,
                    callback_data=f"timezone:{tz_name}",
                )
            ]
        )

    # Add option to type custom timezone
    buttons.append(
        [
            InlineKeyboardButton(
                "Other (type manually)",
                callback_data="timezone:custom",
            )
        ]
    )

    return InlineKeyboardMarkup(buttons)


def build_timezone_region_keyboard() -> InlineKeyboardMarkup:
    """
    Build keyboard for timezone region selection.

    Returns:
        InlineKeyboardMarkup with region buttons
    """
    buttons = []

    for region_key, label in REGION_LABELS.items():
        buttons.append(
            [InlineKeyboardButton(label, callback_data=f"tz_region:{region_key}")]
        )

    # Add option to type custom timezone
    buttons.append(
        [InlineKeyboardButton("Other (type manually)", callback_data="timezone:custom")]
    )

    return InlineKeyboardMarkup(buttons)


def build_timezone_list_keyboard(region: str) -> InlineKeyboardMarkup:
    """
    Build keyboard for timezones in a specific region.

    Args:
        region: Region key (americas, europe, asia_pacific)

    Returns:
        InlineKeyboardMarkup with timezone buttons and back button
    """
    timezones = TIMEZONE_REGIONS.get(region, [])
    buttons = []

    for tz_name, display_name in timezones:
        buttons.append(
            [InlineKeyboardButton(display_name, callback_data=f"timezone:{tz_name}")]
        )

    # Add back button
    buttons.append([InlineKeyboardButton("← Back", callback_data="tz_region:back")])

    return InlineKeyboardMarkup(buttons)


def build_focus_areas_keyboard(
    selected: Optional[set[str]] = None,
) -> InlineKeyboardMarkup:
    """
    Build multi-select keyboard for focus area preferences.

    Args:
        selected: Currently selected areas

    Returns:
        InlineKeyboardMarkup with toggleable area buttons
    """
    selected = selected or set()
    buttons = []

    # Add "All equal" option
    all_selected = len(selected) == 0
    all_marker = "✓ " if all_selected else ""
    buttons.append(
        [
            InlineKeyboardButton(
                f"{all_marker}All areas equally",
                callback_data="focus:all",
            )
        ]
    )

    # Add each content area
    for area in ContentArea:
        is_selected = area.value in selected
        marker = "✓ " if is_selected else ""
        short_name = _get_short_area_name(area)

        buttons.append(
            [
                InlineKeyboardButton(
                    f"{marker}{short_name}",
                    callback_data=f"focus:{area.value}",
                )
            ]
        )

    # Add done button
    buttons.append(
        [
            InlineKeyboardButton(
                "✅ Done",
                callback_data="focus:done",
            )
        ]
    )

    return InlineKeyboardMarkup(buttons)


def build_settings_keyboard() -> InlineKeyboardMarkup:
    """
    Build keyboard for user settings menu.

    Returns:
        InlineKeyboardMarkup with settings options
    """
    buttons = [
        [
            InlineKeyboardButton(
                "🌍 Change Timezone",
                callback_data="settings:timezone",
            )
        ],
        [
            InlineKeyboardButton(
                "📚 Focus Areas",
                callback_data="settings:focus",
            )
        ],
        [
            InlineKeyboardButton(
                "🔔 Subscription",
                callback_data="settings:subscription",
            )
        ],
        [
            InlineKeyboardButton(
                "❌ Close",
                callback_data="settings:close",
            )
        ],
    ]

    return InlineKeyboardMarkup(buttons)


def build_subscription_keyboard(is_subscribed: bool) -> InlineKeyboardMarkup:
    """
    Build keyboard for subscription toggle.

    Args:
        is_subscribed: Current subscription status

    Returns:
        InlineKeyboardMarkup with toggle button
    """
    if is_subscribed:
        text = "🔕 Unsubscribe from daily questions"
        callback = "subscription:off"
    else:
        text = "🔔 Subscribe to daily questions"
        callback = "subscription:on"

    buttons = [
        [InlineKeyboardButton(text, callback_data=callback)],
        [InlineKeyboardButton("« Back", callback_data="settings:menu")],
    ]

    return InlineKeyboardMarkup(buttons)


def build_confirmation_keyboard(
    action: str,
    confirm_data: str,
    cancel_data: str = "cancel",
) -> InlineKeyboardMarkup:
    """
    Build generic confirmation keyboard.

    Args:
        action: Description of the action to confirm
        confirm_data: Callback data for confirm button
        cancel_data: Callback data for cancel button

    Returns:
        InlineKeyboardMarkup with confirm/cancel buttons
    """
    buttons = [
        [
            InlineKeyboardButton("✅ Confirm", callback_data=confirm_data),
            InlineKeyboardButton("❌ Cancel", callback_data=cancel_data),
        ]
    ]

    return InlineKeyboardMarkup(buttons)


def build_report_button(question_id: int) -> InlineKeyboardMarkup:
    """
    Build a single "Report Issue" button to show after answer feedback.

    Args:
        question_id: Question ID for callback data

    Returns:
        InlineKeyboardMarkup with report button
    """
    buttons = [
        [
            InlineKeyboardButton(
                "⚠️ Report Issue",
                callback_data=f"report:{question_id}",
            )
        ]
    ]
    return InlineKeyboardMarkup(buttons)


def build_report_type_keyboard(question_id: int) -> InlineKeyboardMarkup:
    """
    Build keyboard for selecting report type.

    Args:
        question_id: Question ID for callback data

    Returns:
        InlineKeyboardMarkup with report type options
    """
    report_types = [
        ("incorrect_answer", "Incorrect Answer"),
        ("confusing_wording", "Confusing Wording"),
        ("outdated_content", "Outdated Content"),
        ("other", "Other Issue"),
    ]

    buttons = []
    for report_type, label in report_types:
        buttons.append(
            [
                InlineKeyboardButton(
                    label,
                    callback_data=f"report_submit:{question_id}:{report_type}",
                )
            ]
        )

    # Add cancel button
    buttons.append(
        [
            InlineKeyboardButton(
                "❌ Cancel",
                callback_data="report_cancel",
            )
        ]
    )

    return InlineKeyboardMarkup(buttons)


def build_source_expand_keyboard(question_id: int) -> InlineKeyboardMarkup:
    """
    Build keyboard with 'Show Full Quote' button.

    Args:
        question_id: Question ID for callback data

    Returns:
        InlineKeyboardMarkup with expand button
    """
    buttons = [
        [
            InlineKeyboardButton(
                "📖 Show Full Quote",
                callback_data=f"expand_source:{question_id}",
            )
        ]
    ]
    return InlineKeyboardMarkup(buttons)
