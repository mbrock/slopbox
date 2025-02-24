from tagflow import tag, text


class Styles:
    button_primary = [
        "px-2 py-1",
        "text-sm font-semibold",
        "bg-slate-200 text-gray-800",
        "border-1 border-neutral-500",
        "shadow-sm",
        "hover:bg-slate-300",
        "disabled:opacity-50 disabled:cursor-not-allowed",
    ]

    button_secondary = [
        "px-2 py-1",
        "text-xs text-neutral-800",
        "bg-white bg-neutral-300",
        "ring-1 ring-inset ring-neutral-400",
        "hover:bg-neutral-100 hover:text-neutral-900",
    ]

    input_primary = [
        "flex-1 px-2",
        "text-sm",
        "bg-white",
        "border border-neutral-500",
        "placeholder:text-neutral-600 placeholder:italic",
        "field-sizing-content",
    ]

    spec_action_button = [
        "text-xs",
        "px-3 py-1",
        "bg-neutral-100 hover:bg-neutral-200",
        "border border-neutral-400",
    ]

    pagination_button = [
        "px-4",
        "bg-white hover:bg-neutral-100",
        "rounded shadow",
    ]

    pagination_text = ["text-neutral-700"]

    sort_button = [
        "px-3 py-1",
        "text-xs text-neutral-800",
        "bg-white",
        "ring-1 ring-inset ring-neutral-400",
        "hover:bg-neutral-100",
        "first:rounded-l last:rounded-r",
        "-ml-[1px]",  # Overlap borders
    ]

    sort_button_active = [
        *sort_button,
        "bg-neutral-300",
        "hover:bg-neutral-300",
        "relative",  # Ensure border shows on top
        "z-10",
    ]

    filter_button = [
        "px-3 py-1",
        "text-xs text-neutral-800",
        "bg-white",
        "rounded-full",
        "ring-1 ring-inset ring-neutral-400",
        "hover:bg-neutral-100",
        "flex items-center gap-1",
    ]

    filter_button_active = [
        *filter_button,
        "bg-amber-100",
        "hover:bg-amber-200",
        "ring-amber-400",
    ]

    radio_button = [
        "px-3 py-1.5",
        "text-xs text-neutral-800",
        "ring-1 ring-inset ring-neutral-400",
        "first:rounded-l last:rounded-r",
        "-ml-[1px]",
        "cursor-pointer",
        "group",
        "transition-colors",
        "flex-1",
    ]

    radio_button_inactive = [
        *radio_button,
        "bg-white",
        "hover:bg-neutral-200",
    ]

    radio_button_active = [
        *radio_button,
        "bg-neutral-300",
        "hover:bg-neutral-300",
        "relative",
        "z-10",
    ]


def render_radio_option(
    name: str,
    value: str,
    label: str,
    is_checked: bool = False,
):
    """Render a styled radio button option with label.

    Args:
        name: Name attribute for the radio group
        value: Value for this radio option
        label: Display label text
        is_checked: Whether this option is selected
    """
    with tag.div("flex items-center"):
        with tag.input(
            "relative size-4",
            "appearance-none rounded-full",
            "border border-neutral-300 bg-white",
            "before:absolute before:inset-1",
            "before:rounded-full before:bg-white",
            "checked:border-neutral-600 checked:bg-neutral-600",
            "focus-visible:outline focus-visible:outline-2",
            "focus-visible:outline-offset-2 focus-visible:outline-neutral-600",
            "[&:not(:checked)]:before:hidden",
            id=f"{name}-{value}",
            type="radio",
            name=name,
            value=value,
            checked=is_checked,
        ):
            pass
        with tag.label(
            "ml-3 text-sm font-medium text-neutral-900",
            for_=f"{name}-{value}",
        ):
            text(label)
