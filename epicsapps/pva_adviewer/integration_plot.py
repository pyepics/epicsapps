#!/usr/bin/env python
"""
1D azimuthal integration profile plot. Extends wxmplot.LinePlot with PONI overlay, unit buttons, and LiveToggle.
"""

from typing import Callable

import numpy as np
import wx
from vispy import scene
from wxmplot import LinePlot
from wxutils import draw_folder, FlatTextCtrl

from epicsapps.pva_adviewer.theme import AppTheme, get_theme
from epicsapps.pva_adviewer.widgets import LiveToggle, PlotToggleButton

__all__ = ["IntegrationPlot"]


class IntegrationPlot(LinePlot):
    """Azimuthal integration profile plot with PONI overlay and unit buttons."""


    def __init__(self, parent: wx.Window) -> None:
        """Initialise the IntegrationPlot."""
        super().__init__(parent)

        self._poni_text: str = "No calibration loaded"
        self._poni_loaded: bool = False
        self._load_poni_cb: Callable[[], None] | None = None
        self._calibrated: bool = False

        self._active_unit: str = AppTheme.unit_keys[0]
        self._unit_changed_cb: Callable[[str], None] | None = None
        self._unit_btn_rects: list[wx.Rect] = []
        self.UNIT_BTN_Hovered: int = -1
        self._unit_btn_pressed: int = -1

        self._btn_hovered: bool = False
        self._btn_pressed: bool = False
        self._btn_rect: wx.Rect = wx.Rect(0, 0, 0, 0)

        self._bg_active: bool = False
        self._bg_inspect_active: bool = False
        self._bg_changed_cb: Callable[[bool], None] | None = None
        self._bg_inspect_changed_cb: Callable[[bool], None] | None = None

        # Background curve visual (orange-red, shown in inspect mode)
        self._bkg_line = scene.visuals.Line(
            pos=np.array([[0, 0], [1, 0]], dtype=np.float32),
            color=(1.0, 0.45, 0.15, 1.0),
            width=1.5,
            method="agg",
            parent=self._view.scene,
        )
        self._bkg_line.visible = False

        # ROI region visuals — mesh first so handle lines always render on top
        _roi_y = 1e10
        self._roi_mesh = scene.visuals.Mesh(
            vertices=np.zeros((4, 2), dtype=np.float32),
            faces=np.array([[0, 1, 2], [0, 2, 3]], dtype=np.uint32),
            color=(0.4, 0.7, 1.0, 0.10),
            parent=self._view.scene,
        )
        self._roi_mesh.visible = False
        self._roi_left_line = scene.visuals.Line(
            pos=np.array([[0, -_roi_y], [0, _roi_y]], dtype=np.float32),
            color=(0.6, 0.85, 1.0, 1.0),
            width=3,
            method="agg",
            parent=self._view.scene,
        )
        self._roi_left_line.visible = False
        self._roi_right_line = scene.visuals.Line(
            pos=np.array([[1, -_roi_y], [1, _roi_y]], dtype=np.float32),
            color=(0.6, 0.85, 1.0, 1.0),
            width=3,
            method="agg",
            parent=self._view.scene,
        )
        self._roi_right_line.visible = False

        # ROI drag state
        self._roi_visible: bool = False
        self._roi_x_min: float = 0.0
        self._roi_x_max: float = 1.0
        self._roi_dragging: int = 0
        self._roi_changed_cb: Callable[[float, float], None] | None = None

        # Canvas bindings for ROI drag
        self._canvas.native.Bind(wx.EVT_LEFT_DOWN, self._on_roi_canvas_down)
        self._canvas.native.Bind(wx.EVT_MOTION, self._on_roi_canvas_move)
        self._canvas.native.Bind(wx.EVT_LEFT_UP, self._on_roi_canvas_up)

        self._bg_btn = PlotToggleButton(self, label="b", tooltip="Toggle auto background subtraction")
        self._bg_btn.SetAction(self._on_bg_toggled)
        self._bg_btn.Hide()

        self._inspect_btn = PlotToggleButton(self, label="I", tooltip="Inspect / adjust background ROI")
        self._inspect_btn.SetAction(self._on_inspect_toggled)
        self._inspect_btn.Hide()

        self._poly_order_changed_cb: Callable[[int], None] | None = None
        self._poly_order_ctrl = FlatTextCtrl(
            self, value="50", centered=True,
            size=wx.Size(36, AppTheme.live_w), corner_radius=4,
        )
        self._poly_order_ctrl.SetToolTip("Chebyshev polynomial order for background fit")
        self._poly_order_ctrl.Bind(wx.EVT_TEXT_ENTER, self._on_poly_order_enter)
        self._poly_order_ctrl.Bind(wx.EVT_KILL_FOCUS, self._on_poly_order_enter)
        self._poly_order_ctrl.Hide()

        self._live_toggle = LiveToggle(self, live=False, tooltip="Toggle live ROI integration")
        self._live_toggle.Hide()

        self.Bind(wx.EVT_MOTION, self._on_integration_mouse_move)
        self.Bind(wx.EVT_LEAVE_WINDOW, self._on_integration_mouse_leave)
        self.Bind(wx.EVT_LEFT_DOWN, self._on_integration_mouse_down)
        self.Bind(wx.EVT_LEFT_UP, self._on_integration_mouse_up)

        wx.CallAfter(self._reposition_children)

    def _on_size(self, event: wx.SizeEvent) -> None:
        super()._on_size(event)
        self._reposition_children()

    def set_poni_info(self, text: str, success: bool) -> None:
        """Update the PONI calibration status text and color."""
        self._poni_text = text
        self._poni_loaded = success
        self.Refresh()

    def set_load_poni_callback(self, callback: Callable[[], None]) -> None:
        """Register a callback to invoke when the load-PONI button is clicked."""
        self._load_poni_cb = callback

    def set_unit_changed_callback(self, callback: Callable[[str], None]) -> None:
        """Register a callback fired with the new unit key when the user switches units."""
        self._unit_changed_cb = callback

    def set_live_integration_callback(self, callback: Callable[[bool], None]) -> None:
        """Register a callback fired with the live toggle state."""
        self._live_toggle.set_toggled_callback(callback)

    def set_bg_callback(self, callback: Callable[[bool], None]) -> None:
        """Register a callback fired with the bg toggle state."""
        self._bg_changed_cb = callback

    def set_bg_inspect_callback(self, callback: Callable[[bool], None]) -> None:
        """Register a callback fired with the inspect (I) toggle state."""
        self._bg_inspect_changed_cb = callback

    def set_bg_active(self, active: bool) -> None:
        """Programmatically set the bg button state."""
        self._bg_active = active
        self._bg_btn.SetValue(active)
        if not active:
            self._bg_inspect_active = False
            self._inspect_btn.SetValue(False)
            self._inspect_btn.Hide()
            self._poly_order_ctrl.Hide()
        else:
            self._inspect_btn.Show()
        self._reposition_children()

    def set_bg_inspect_active(self, active: bool) -> None:
        """Programmatically set the inspect (I) button state."""
        self._bg_inspect_active = active and self._bg_active
        self._inspect_btn.SetValue(self._bg_inspect_active)
        self._poly_order_ctrl.Show(self._bg_inspect_active)
        self._reposition_children()

    def set_poly_order_callback(self, callback: Callable[[int], None]) -> None:
        """Register a callback fired with the new polynomial order when the user changes it."""
        self._poly_order_changed_cb = callback

    def _on_poly_order_enter(self, event: wx.Event) -> None:
        try:
            order = max(1, min(200, int(self._poly_order_ctrl.GetValue().strip())))
        except ValueError:
            order = 50
        self._poly_order_ctrl.SetValue(str(order))
        if self._poly_order_changed_cb is not None:
            self._poly_order_changed_cb(order)
        event.Skip()

    @property
    def bg_active(self) -> bool:
        return self._bg_active

    @property
    def bg_inspect_active(self) -> bool:
        return self._bg_inspect_active

    def set_bkg_data(self, xs: np.ndarray, ys: np.ndarray) -> None:
        """Show the background curve overlay (used in inspect mode)."""
        pts = np.column_stack([xs, ys]).astype(np.float32)
        self._bkg_line.set_data(pos=pts)
        self._bkg_line.visible = True
        self._canvas.update()

    def clear_bkg_data(self) -> None:
        """Hide the background curve overlay."""
        self._bkg_line.visible = False
        self._canvas.update()

    def set_bkg_roi_changed_callback(self, callback: Callable[[float, float], None]) -> None:
        self._roi_changed_cb = callback

    def show_bkg_roi(self, x_min: float, x_max: float) -> None:
        """Show the draggable ROI region between x_min and x_max."""
        self._roi_x_min = x_min
        self._roi_x_max = x_max
        self._roi_visible = True
        self._update_roi_visuals()

    def hide_bkg_roi(self) -> None:
        """Hide the ROI region."""
        self._roi_visible = False
        self._roi_left_line.visible = False
        self._roi_right_line.visible = False
        self._roi_mesh.visible = False
        self._canvas.update()

    def get_bkg_roi(self) -> tuple[float, float]:
        return self._roi_x_min, self._roi_x_max

    def set_bkg_roi(self, x_min: float, x_max: float) -> None:
        self._roi_x_min = x_min
        self._roi_x_max = x_max
        if self._roi_visible:
            self._update_roi_visuals()

    def _update_roi_visuals(self) -> None:
        _Y = 1e10
        xL, xR = self._roi_x_min, self._roi_x_max
        self._roi_left_line.set_data(pos=np.array([[xL, -_Y], [xL, _Y]], dtype=np.float32))
        self._roi_left_line.visible = True
        self._roi_right_line.set_data(pos=np.array([[xR, -_Y], [xR, _Y]], dtype=np.float32))
        self._roi_right_line.visible = True
        ranges = self._data_ranges()
        if ranges is not None:
            _, _, y_min, y_max = ranges
            verts = np.array(
                [[xL, y_min], [xR, y_min], [xR, y_max], [xL, y_max]],
                dtype=np.float32,
            )
            self._roi_mesh.set_data(
                vertices=verts,
                faces=np.array([[0, 1, 2], [0, 2, 3]], dtype=np.uint32),
                color=(0.4, 0.7, 1.0, 0.10),
            )
            self._roi_mesh.visible = True
        self._canvas.update()

    def _roi_handle_at(self, canvas_x: int, canvas_y: int) -> int:
        """Return 1 for left handle, 2 for right handle, 0 for neither."""
        if not self._roi_visible:
            return 0
        panel_pt = self._canvas_pt_to_panel(canvas_x, canvas_y)
        result = self._panel_pt_to_data(panel_pt)
        if result is None:
            return 0
        data_x, _ = result
        ranges = self._data_ranges()
        if ranges is None:
            return 0
        W, _ = self.GetSize()
        pw = max(1, W - self._ml - self._mr)
        x_min_d, x_max_d, _, _ = ranges
        if x_max_d == x_min_d:
            return 0
        threshold = 8.0 * (x_max_d - x_min_d) / pw
        dist_l = abs(data_x - self._roi_x_min)
        dist_r = abs(data_x - self._roi_x_max)
        if dist_l < threshold and dist_l <= dist_r:
            return 1
        if dist_r < threshold:
            return 2
        return 0

    def _on_roi_canvas_down(self, event: wx.MouseEvent) -> None:
        raw = event.GetPosition()
        handle = self._roi_handle_at(raw.x, raw.y)
        if handle:
            self._roi_dragging = handle
            return
        event.Skip()

    def _on_roi_canvas_move(self, event: wx.MouseEvent) -> None:
        raw = event.GetPosition()
        if self._roi_dragging:
            panel_pt = self._canvas_pt_to_panel(raw.x, raw.y)
            result = self._panel_pt_to_data(panel_pt)
            if result is not None:
                data_x, _ = result
                ranges = self._data_ranges()
                if ranges is not None:
                    x_min_d, x_max_d, _, _ = ranges
                    data_x = max(x_min_d, min(x_max_d, data_x))
                if self._roi_dragging == 1:
                    self._roi_x_min = min(data_x, self._roi_x_max - 1e-9)
                else:
                    self._roi_x_max = max(data_x, self._roi_x_min + 1e-9)
                self._update_roi_visuals()
            return
        if self._roi_visible:
            handle = self._roi_handle_at(raw.x, raw.y)
            cursor = wx.Cursor(wx.CURSOR_SIZEWE) if handle else wx.NullCursor
            self._canvas.native.SetCursor(cursor)
        event.Skip()

    def _on_roi_canvas_up(self, event: wx.MouseEvent) -> None:
        if self._roi_dragging:
            self._roi_dragging = 0
            if self._roi_changed_cb is not None:
                self._roi_changed_cb(self._roi_x_min, self._roi_x_max)
            return
        event.Skip()

    def set_calibrated(self, calibrated: bool) -> None:
        """Show or hide the unit buttons and live toggle based on calibration state."""
        self._calibrated = calibrated
        if calibrated:
            self._live_toggle.Show()
            self._bg_btn.Show()
        else:
            self._live_toggle.set_live(False)
            self._live_toggle.Hide()
            self._bg_btn.Hide()
            self._bg_active = False
            self._bg_btn.SetValue(False)
            self._bg_inspect_active = False
            self._inspect_btn.SetValue(False)
            self._inspect_btn.Hide()
            self._poly_order_ctrl.Hide()
        self._reposition_children()
        self.Refresh()

    def set_active_unit(self, unit: str) -> None:
        """Set the active unit button by key."""
        if unit in AppTheme.unit_keys:
            self._active_unit = unit
            self.Refresh()

    @property
    def is_live_integration(self) -> bool:
        """Whether live ROI integration is currently active."""
        return self._live_toggle.is_live

    def format_hover_info(self, x: float, y: float) -> str:
        """Return hover info using the active unit label."""
        return f"{self._x_label}: {x:.4g}   I: {y:.4g}"

    def draw_overlays(self, gc: wx.GraphicsContext, W: int, H: int) -> None:
        """Draw the PONI overlay and, when calibrated, the unit buttons."""
        self._draw_poni_overlay(gc, W, H)
        if self._calibrated:
            self._draw_unit_buttons(gc, W, H)

    def _reposition_children(self) -> None:
        """Reposition the VisPy canvas and right-side widget stack within the panel."""
        self._reposition_canvas()
        W, H = self.GetSize()
        canvas_h = max(1, H - self._mt - self._mb)
        right_edge = W - AppTheme.btn_pad

        # Compute total height of the right-side stack so it can be centred
        total_h = AppTheme.live_h
        if self._calibrated:
            total_h += AppTheme.btn_pad + AppTheme.live_w
            if self._bg_active:
                total_h += AppTheme.btn_pad + AppTheme.live_w

        y = self._mt + max(0, (canvas_h - total_h) // 2)

        self._live_toggle.SetPosition(wx.Point(right_edge - AppTheme.live_w, y))
        self._live_toggle.Raise()
        y += AppTheme.live_h

        if self._calibrated:
            y += AppTheme.btn_pad
            self._bg_btn.SetPosition(wx.Point(right_edge - AppTheme.live_w, y))
            self._bg_btn.Raise()
            y += AppTheme.live_w

            if self._bg_active:
                y += AppTheme.btn_pad
                inspect_x = right_edge - AppTheme.live_w
                self._inspect_btn.SetPosition(wx.Point(inspect_x, y))
                self._inspect_btn.Raise()

                if self._bg_inspect_active:
                    poly_w = self._poly_order_ctrl.GetSize().width
                    self._poly_order_ctrl.SetPosition(
                        wx.Point(inspect_x - AppTheme.btn_pad - poly_w, y)
                    )
                    self._poly_order_ctrl.Raise()

    def _on_bg_toggled(self, _event: wx.CommandEvent) -> None:
        self._bg_active = self._bg_btn.GetValue()
        if not self._bg_active:
            self._bg_inspect_active = False
            self._inspect_btn.SetValue(False)
            self._inspect_btn.Hide()
            self._poly_order_ctrl.Hide()
            if self._bg_inspect_changed_cb is not None:
                self._bg_inspect_changed_cb(False)
        else:
            self._inspect_btn.Show()
        self._reposition_children()
        if self._bg_changed_cb is not None:
            self._bg_changed_cb(self._bg_active)

    def _on_inspect_toggled(self, _event: wx.CommandEvent) -> None:
        self._bg_inspect_active = self._inspect_btn.GetValue()
        self._poly_order_ctrl.Show(self._bg_inspect_active)
        self._reposition_children()
        if self._bg_inspect_changed_cb is not None:
            self._bg_inspect_changed_cb(self._bg_inspect_active)

    def _btn_rect_for(self, W: int, H: int) -> wx.Rect:
        """Return the bounding rect of the load-PONI button."""
        return wx.Rect(W - AppTheme.btn_w - AppTheme.btn_pad, H - AppTheme.btn_h - AppTheme.btn_pad, AppTheme.btn_w, AppTheme.btn_h)

    def _unit_btn_at(self, pt: wx.Point) -> int:
        """Return the index of the unit button under pt, or -1."""
        for i, r in enumerate(self._unit_btn_rects):
            if r.Contains(pt):
                return i
        return -1

    def _overlay_buttons(self) -> list:
        return [self._live_toggle, self._bg_btn, self._inspect_btn]

    def _on_integration_mouse_move(self, event: wx.MouseEvent) -> None:
        """Update button hover state in addition to base hover logic."""
        pt = event.GetPosition()
        W, H = self.GetSize()
        inside_btn = self._btn_rect_for(W, H).Contains(pt)
        if inside_btn != self._btn_hovered:
            self._btn_hovered = inside_btn
            self.Refresh()
        if self._calibrated:
            idx = self._unit_btn_at(pt)
            if idx != self.UNIT_BTN_Hovered:
                self.UNIT_BTN_Hovered = idx
                self.Refresh()
        for btn in self._overlay_buttons():
            if btn.IsShown():
                pos = btn.GetPosition()
                sz = btn.GetSize()
                btn.set_hovered(wx.Rect(pos.x, pos.y, sz.width, sz.height).Contains(pt))
        event.Skip()

    def _on_integration_mouse_leave(self, event: wx.MouseEvent) -> None:
        for btn in self._overlay_buttons():
            btn.set_hovered(False)
        event.Skip()

    def _on_integration_mouse_down(self, event: wx.MouseEvent) -> None:
        """Handle clicks on the PONI button and unit buttons."""
        pt = event.GetPosition()
        W, H = self.GetSize()
        if self._btn_rect_for(W, H).Contains(pt):
            self._btn_pressed = True
            self.Refresh()
            event.Skip()
            return
        if self._calibrated:
            idx = self._unit_btn_at(pt)
            if idx != -1:
                self._unit_btn_pressed = idx
                self.Refresh()
                event.Skip()
                return
        event.Skip()

    def _on_integration_mouse_up(self, event: wx.MouseEvent) -> None:
        """Fire PONI and unit callbacks on button release."""
        pt = event.GetPosition()
        W, H = self.GetSize()
        was_btn = self._btn_pressed
        was_unit = self._unit_btn_pressed
        self._btn_pressed = False
        self._unit_btn_pressed = -1
        self.Refresh()
        if was_btn and self._btn_rect_for(W, H).Contains(pt) and self._load_poni_cb is not None:
            self._load_poni_cb()
        if was_unit != -1 and self._unit_btn_at(pt) == was_unit:
            self._active_unit = AppTheme.unit_keys[was_unit]
            if self._unit_changed_cb is not None:
                self._unit_changed_cb(self._active_unit)
        event.Skip()

    def _draw_unit_buttons(self, gc: wx.GraphicsContext, W: int, H: int) -> None:
        """Paint the 2θ / d / Q unit selector buttons."""
        t = get_theme()
        fg = t.foreground
        bg = t.background
        bg_hover = t.white
        border = t.white

        total_w = len(AppTheme.unit_keys) * AppTheme.unit_btn_w + (len(AppTheme.unit_keys) - 1) * AppTheme.unit_btn_gap
        start_x = W - self._mr - total_w
        self._unit_btn_rects = []
        font = AppTheme.scaled_font(9, weight=wx.FONTWEIGHT_BOLD)
        for i, (key, label) in enumerate(zip(AppTheme.unit_keys, AppTheme.unit_labels)):
            x = start_x + i * (AppTheme.unit_btn_w + AppTheme.unit_btn_gap)
            r = wx.Rect(x, 2, AppTheme.unit_btn_w, AppTheme.unit_btn_h)
            self._unit_btn_rects.append(r)
            active = key == self._active_unit
            green = t.green
            if i == self._unit_btn_pressed:
                b, brd, f = t.bright_black, green if active else border, green if active else fg
            elif active:
                b, brd, f = wx.Colour(green.Red(), green.Green(), green.Blue(), 40), green, green
            elif i == self.UNIT_BTN_Hovered:
                b, brd, f = bg_hover, border, fg
            else:
                b, brd, f = bg, border, fg
            gc.SetBrush(wx.Brush(b))
            gc.SetPen(wx.Pen(brd, 1))
            gc.DrawRoundedRectangle(r.x, r.y, r.width, r.height, 3)
            gc.SetFont(font, f)
            tw, th = gc.GetTextExtent(label)
            gc.DrawText(label, r.x + (r.width - tw) / 2, r.y + (r.height - th) / 2)

    def _draw_poni_overlay(self, gc: wx.GraphicsContext, W: int, H: int) -> None:
        """Paint the load-PONI button, calibration status text, and hover/max info."""
        t = get_theme()
        btn_hover = t.white
        btn_press = t.bright_black

        br = self._btn_rect_for(W, H)
        self._btn_rect = br
        bg = btn_press if self._btn_pressed else (btn_hover if self._btn_hovered else t.background)
        gc.SetBrush(wx.Brush(bg))
        gc.SetPen(wx.TRANSPARENT_PEN)
        gc.DrawRoundedRectangle(br.x, br.y, br.width, br.height, 4)
        gc.SetAntialiasMode(wx.ANTIALIAS_DEFAULT)
        off = (br.width - AppTheme.icon_size) / 2
        gc.PushState()
        gc.Translate(br.x + off, br.y + off)
        draw_folder(gc, AppTheme.icon_size)
        gc.PopState()

        font = AppTheme.scaled_font(11, style=wx.FONTSTYLE_ITALIC)
        gc.SetFont(font, get_theme().green if self._poni_loaded else get_theme().white)
        tw, th = gc.GetTextExtent(self._poni_text)
        gc.DrawText(self._poni_text, br.x - tw - AppTheme.btn_pad, br.y + (br.height - th) / 2)

        info_font = AppTheme.scaled_font(11, weight=wx.FONTWEIGHT_BOLD)
        gc.SetFont(info_font, t.green)
        x = AppTheme.btn_pad
        if self.ys is not None and self.ys.size > 0:
            lbl = f"max: {float(self.ys.max()):.4g}"
            lw, lh = gc.GetTextExtent(lbl)
            gc.DrawText(lbl, x, br.y + (br.height - lh) / 2)
            x += lw + 16
        if self._hover_data_x is not None and self._hover_data_y is not None:
            coord = self.format_hover_info(self._hover_data_x, self._hover_data_y)
            _, ch = gc.GetTextExtent(coord)
            gc.DrawText(coord, x, br.y + (br.height - ch) / 2)
