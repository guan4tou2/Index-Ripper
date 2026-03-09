from __future__ import annotations


def apply_app_theme(ctk):
    ctk.set_appearance_mode("system")
    ctk.set_default_color_theme("blue")


def ui_tokens():
    return {
        "option_menu": {
            "height": 34,
            "fg_color": ("#E2E8F0", "#334155"),
            "button_color": ("#CBD5E1", "#475569"),
            "button_hover_color": ("#94A3B8", "#64748B"),
            "text_color": ("#0F172A", "#F8FAFC"),
            "dropdown_fg_color": ("#FFFFFF", "#1E293B"),
            "dropdown_text_color": ("#0F172A", "#F1F5F9"),
            "dropdown_hover_color": ("#E2E8F0", "#334155"),
        },
        "tabview": {
            "segmented_button_fg_color": ("#E2E8F0", "#334155"),
            "segmented_button_selected_color": ("#2563EB", "#3B82F6"),
            "segmented_button_selected_hover_color": ("#1D4ED8", "#2563EB"),
            "segmented_button_unselected_color": ("#CBD5E1", "#475569"),
            "segmented_button_unselected_hover_color": ("#94A3B8", "#64748B"),
            "text_color": ("#0F172A", "#F8FAFC"),
        },
        "checkbox": {
            "checkbox_width": 20,
            "checkbox_height": 20,
            "corner_radius": 6,
            "border_width": 2,
            "border_color": ("#94A3B8", "#64748B"),
            "fg_color": ("#2563EB", "#3B82F6"),
            "hover_color": ("#1D4ED8", "#2563EB"),
            "checkmark_color": ("#FFFFFF", "#FFFFFF"),
            "text_color": ("#0F172A", "#E2E8F0"),
        },
        "logs": {
            "height": 100,
            "font": ("SF Mono", 12),
            "text_color": ("#0F172A", "#E2E8F0"),
            "fg_color": ("#F8FAFC", "#111827"),
        },
        "downloads": {
            "row_fg_color": ("#FFFFFF", "#1F2937"),
            "row_border_width": 1,
            "row_corner_radius": 10,
            "name_text_color": ("#0F172A", "#E2E8F0"),
            "status_colors": {
                "queued": ("#475569", "#94A3B8"),
                "active": ("#1D4ED8", "#60A5FA"),
                "warning": ("#B45309", "#F59E0B"),
                "success": ("#047857", "#34D399"),
                "error": ("#B91C1C", "#F87171"),
            },
            "cancel_button": {
                "width": 88,
                "height": 30,
                "fg_color": "#DC2626",
                "hover_color": "#B91C1C",
            },
        },
    }


def action_button_style_name(kind: str) -> str:
    mapping = {
        "primary": "Primary.TButton",
        "secondary": "Secondary.TButton",
        "danger": "Danger.TButton",
        "success": "Success.TButton",
    }
    return mapping.get(kind, "Secondary.TButton")


def configure_action_button_styles(window, ctk, ttk):
    style = ttk.Style()
    text_light = "#F8FAFC"
    fg = {
        "primary": window._apply_appearance_mode(("#2563EB", "#3B82F6")),
        "secondary": window._apply_appearance_mode(("#334155", "#475569")),
        "danger": window._apply_appearance_mode(("#DC2626", "#EF4444")),
        "success": window._apply_appearance_mode(("#059669", "#10B981")),
    }
    active = {
        "primary": window._apply_appearance_mode(("#1D4ED8", "#2563EB")),
        "secondary": window._apply_appearance_mode(("#1E293B", "#334155")),
        "danger": window._apply_appearance_mode(("#B91C1C", "#DC2626")),
        "success": window._apply_appearance_mode(("#047857", "#059669")),
    }
    for kind in ("primary", "secondary", "danger", "success"):
        style_name = action_button_style_name(kind)
        style.configure(
            style_name,
            padding=(12, 7),
            foreground=text_light,
            background=fg[kind],
            borderwidth=0,
            focusthickness=1,
            focuscolor=active[kind],
            font=("SF Pro Text", 11, "bold"),
        )
        style.map(
            style_name,
            background=[("active", active[kind]), ("disabled", "#6B7280")],
            foreground=[("disabled", "#E5E7EB")],
        )


def ui_tokens():
    return {
        "option_menu": {
            "height": 34,
            "fg_color": ("#E2E8F0", "#334155"),
            "button_color": ("#CBD5E1", "#475569"),
            "button_hover_color": ("#94A3B8", "#64748B"),
            "text_color": ("#0F172A", "#F8FAFC"),
            "dropdown_fg_color": ("#FFFFFF", "#1E293B"),
            "dropdown_text_color": ("#0F172A", "#F1F5F9"),
            "dropdown_hover_color": ("#E2E8F0", "#334155"),
        },
        "tabview": {
            "segmented_button_fg_color": ("#E2E8F0", "#334155"),
            "segmented_button_selected_color": ("#2563EB", "#3B82F6"),
            "segmented_button_selected_hover_color": ("#1D4ED8", "#2563EB"),
            "segmented_button_unselected_color": ("#CBD5E1", "#475569"),
            "segmented_button_unselected_hover_color": ("#94A3B8", "#64748B"),
            "text_color": ("#0F172A", "#F8FAFC"),
        },
        "checkbox": {
            "checkbox_width": 20,
            "checkbox_height": 20,
            "corner_radius": 6,
            "border_width": 2,
            "border_color": ("#94A3B8", "#64748B"),
            "fg_color": ("#2563EB", "#3B82F6"),
            "hover_color": ("#1D4ED8", "#2563EB"),
            "checkmark_color": ("#FFFFFF", "#FFFFFF"),
            "text_color": ("#0F172A", "#E2E8F0"),
        },
        "logs": {
            "height": 100,
            "font": ("SF Mono", 12),
            "text_color": ("#0F172A", "#E2E8F0"),
            "fg_color": ("#F8FAFC", "#111827"),
        },
        "downloads": {
            "row_fg_color": ("#FFFFFF", "#1F2937"),
            "row_border_width": 1,
            "row_corner_radius": 10,
            "name_text_color": ("#0F172A", "#E2E8F0"),
            "status_colors": {
                "queued": ("#475569", "#94A3B8"),
                "active": ("#1D4ED8", "#60A5FA"),
                "warning": ("#B45309", "#F59E0B"),
                "success": ("#047857", "#34D399"),
                "error": ("#B91C1C", "#F87171"),
            },
            "cancel_button": {
                "width": 88,
                "height": 30,
                "fg_color": "#DC2626",
                "hover_color": "#B91C1C",
            },
        },
    }


def action_button_style_name(kind: str) -> str:
    mapping = {
        "primary": "Primary.TButton",
        "secondary": "Secondary.TButton",
        "danger": "Danger.TButton",
        "success": "Success.TButton",
    }
    return mapping.get(kind, "Secondary.TButton")


def configure_action_button_styles(window, ctk, ttk):
    style = ttk.Style()
    text_light = "#F8FAFC"
    fg = {
        "primary": window._apply_appearance_mode(("#2563EB", "#3B82F6")),
        "secondary": window._apply_appearance_mode(("#334155", "#475569")),
        "danger": window._apply_appearance_mode(("#DC2626", "#EF4444")),
        "success": window._apply_appearance_mode(("#059669", "#10B981")),
    }
    active = {
        "primary": window._apply_appearance_mode(("#1D4ED8", "#2563EB")),
        "secondary": window._apply_appearance_mode(("#1E293B", "#334155")),
        "danger": window._apply_appearance_mode(("#B91C1C", "#DC2626")),
        "success": window._apply_appearance_mode(("#047857", "#059669")),
    }
    for kind in ("primary", "secondary", "danger", "success"):
        style_name = action_button_style_name(kind)
        style.configure(
            style_name,
            padding=(12, 7),
            foreground=text_light,
            background=fg[kind],
            borderwidth=0,
            focusthickness=1,
            focuscolor=active[kind],
            font=("SF Pro Text", 11, "bold"),
        )
        style.map(
            style_name,
            background=[("active", active[kind]), ("disabled", "#6B7280")],
            foreground=[("disabled", "#E5E7EB")],
        )


def configure_treeview_style(window, ctk, ttk):
    style = ttk.Style()
    bg_color = window._apply_appearance_mode(ctk.ThemeManager.theme["CTkFrame"]["fg_color"])
    text_color = window._apply_appearance_mode(
        ctk.ThemeManager.theme["CTkLabel"]["text_color"]
    )
    selected_color = window._apply_appearance_mode(
        ctk.ThemeManager.theme["CTkButton"]["fg_color"]
    )

    style.theme_use("default")
    style.configure(
        "Treeview",
        background=bg_color,
        foreground=text_color,
        fieldbackground=bg_color,
        borderwidth=0,
        rowheight=28,
        font=("SF Pro Text", 12),
    )
    style.map(
        "Treeview",
        background=[("selected", selected_color)],
        foreground=[("selected", "#FFFFFF")],
    )
    style.configure(
        "Treeview.Heading",
        background=window._apply_appearance_mode(
            ctk.ThemeManager.theme["CTkFrame"]["top_fg_color"]
        ),
        foreground=text_color,
        relief="flat",
        font=("SF Pro Text", 11, "bold"),
    )
    style.map(
        "Treeview.Heading",
        background=[
            (
                "active",
                window._apply_appearance_mode(
                    ctk.ThemeManager.theme["CTkButton"]["hover_color"]
                ),
            )
        ],
    )


def treeview_tag_colors(window):
    return {
        "oddrow": window._apply_appearance_mode(("#FFFFFF", "#2A2D35")),
        "evenrow": window._apply_appearance_mode(("#F8FAFC", "#242831")),
        "checked": window._apply_appearance_mode(("#0F766E", "#2DD4BF")),
    }
