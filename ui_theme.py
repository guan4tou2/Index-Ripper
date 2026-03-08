from __future__ import annotations


def apply_app_theme(ctk):
    ctk.set_appearance_mode("system")
    ctk.set_default_color_theme("green")


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
        rowheight=22,
    )
    style.map("Treeview", background=[("selected", selected_color)])
    style.configure(
        "Treeview.Heading",
        background=window._apply_appearance_mode(
            ctk.ThemeManager.theme["CTkFrame"]["top_fg_color"]
        ),
        foreground=text_color,
        relief="flat",
        font=("Segoe UI", 10, "bold"),
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
        "oddrow": window._apply_appearance_mode(("#F8FAFC", "#2B2B2B")),
        "evenrow": window._apply_appearance_mode(("#F1F5F9", "#2E2E2E")),
        "checked": window._apply_appearance_mode(("#166534", "#50C878")),
    }
