# -*- encoding:utf-8 -*-

from gi.repository import Gtk, Gdk, Gedit
import re
import os.path
import shutil

ui_str = """<ui>
  <menubar name="MenuBar">
    <menu name="ToolsMenu" action="Tools">
      <placeholder name="ToolsOps_0">
        <separator/>
        <menu name="ClickRegexMenu" action="ClickRegexMenu">
          <placeholder name="ClickRegexMenuHolder">
            <menuitem name="click_regex_configure" action="click_regex_configure"/>
          </placeholder>
        </menu>
        <separator/>
      </placeholder>
    </menu>
  </menubar>
</ui>
"""

def spit(obj):
    print( str(obj) )

class ClickRegexWindowHelper:
  def __init__(self, plugin, window):
    self._window = window
    self._plugin = plugin

    # connect all present views
    views = self._window.get_views()
    for view in views:
      self.connect_view(view)

    # connect all future views
    self.active_tab_added_id = self._window.connect("tab-added", self.tab_added_action)

    self._insert_menu()

  def deactivate(self):
    # Remove any installed menu items?
    # self._remove_menu()
    self._window.disconnect(self.active_tab_added_id)

  def _insert_menu(self):
    # Get the GtkUIManager
    manager = self._window.get_ui_manager()

    # Create a new action group
    self._action_group = Gtk.ActionGroup("ClickRegexActions")
    self._action_group.add_actions( [("ClickRegexMenu", None, _('Click Regex'))] + \
                    [("click_regex_configure", None, _("Configuration"), None, _("Click Regex Configure"), self.click_regex_configure)])

    # Insert the action group
    manager.insert_action_group(self._action_group, -1)

    # Merge the UI
    self._ui_id = manager.add_ui_from_string(ui_str)

  def _remove_menu(self):
    # Get the GtkUIManager
    manager = self._window.get_ui_manager()

    # Remove the ui
    manager.remove_ui(self._ui_id)

    # Remove the action group
    manager.remove_action_group(self._action_group)

    # Make sure the manager updates
    manager.ensure_update()

  def update_ui(self):
    self._action_group.set_sensitive(self._window.get_active_document() != None)

  # connect any listeners that should watch the view
  # they will die with it, so no need to worry about disconnect
  def connect_view(self, view):
    view.connect('button-press-event', self.on_view_button_press_event)

  # connect the view of the new tab
  def tab_added_action(self, action, tab):
    view = tab.get_view()
    self.connect_view(view)

  def click_regex_configure(self, action, data = None):
    # open config.json file
    pass

  def on_view_button_press_event(self, view, event):
    # handle left double click
    if event.button == 1 and event.type == Gdk.EventType._2BUTTON_PRESS:
      click_iter = self._get_click_iter(view, event)
      spit('hey')

  def _get_click_iter(self, view, event):
      """Return the current cursor location based on the click location."""
      buffer_x, buffer_y = view.window_to_buffer_coords(
                      view.get_window_type(event.window),
                      int(event.x),
                      int(event.y))
      event_iter = view.get_iter_at_location(buffer_x, buffer_y)
      return event_iter