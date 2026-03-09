import unittest

import ui_theme


class TestUITheme(unittest.TestCase):
    def test_action_button_style_name(self):
        self.assertEqual(ui_theme.action_button_style_name("primary"), "Primary.TButton")
        self.assertEqual(
            ui_theme.action_button_style_name("secondary"), "Secondary.TButton"
        )
        self.assertEqual(ui_theme.action_button_style_name("danger"), "Danger.TButton")
        self.assertEqual(
            ui_theme.action_button_style_name("success"), "Success.TButton"
        )
        self.assertEqual(ui_theme.action_button_style_name("unknown"), "Secondary.TButton")

    def test_ui_tokens_contains_modern_widget_styles(self):
        tokens = ui_theme.ui_tokens()
        self.assertIn("option_menu", tokens)
        self.assertIn("tabview", tokens)
        self.assertIn("checkbox", tokens)
        self.assertIn("fg_color", tokens["option_menu"])
        self.assertIn("segmented_button_fg_color", tokens["tabview"])
        self.assertIn("border_color", tokens["checkbox"])

    def test_apply_bootstrap_theme_not_present(self):
        self.assertFalse(hasattr(ui_theme, "apply_bootstrap_theme"))


if __name__ == "__main__":
    unittest.main()
