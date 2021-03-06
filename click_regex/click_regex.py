# -*- encoding:utf-8 -*-

from gi.repository import Gtk, Gdk, Gedit, Gio, GLib
import re
import json
import inspect, os, sys

ui_str = """<ui>
  <menubar name="MenuBar">
    <menu name="ToolsMenu" action="Tools">
      <placeholder name="ToolsOps_0">
        <separator/>
        <menu name="ClickRegexMenu" action="ClickRegexMenu">
          <placeholder name="ClickRegexMenuHolder">
            <menuitem name="click_regex_configure" action="click_regex_configure"/>
            <menuitem name="click_regex_reload" action="click_regex_reload"/>
          </placeholder>
        </menu>
        <separator/>
      </placeholder>
    </menu>
  </menubar>
</ui>
"""

def spit(obj):
    print( 'click_regex: ' + str(obj) )

class ClickRegexWindowHelper:
  def __init__(self, plugin, window):
    self._window = window
    self._plugin = plugin

    self.config_file = self.get_config_file_path()
    self.config = {}
    self.reload_config()

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
    self._action_group.add_actions( [("ClickRegexMenu", None, 'Click Regex')] + \
                    [("click_regex_reload", None, "Reload configuration", None, None, self.click_regex_reload)] + \
                    [("click_regex_configure", None, "Edit configuration", None, None, self.click_regex_configure)])

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
    location = Gio.File.new_for_uri("file://" + self.config_file)
    tab = self._window.get_tab_from_location(location)
    if tab is None:
      tab = self._window.create_tab_from_location(location, None,
                                      1, 1, False, True)
      view = tab.get_view()
      doc = self._window.get_active_document()
      doc.connect('saved', self.on_saved_config_file)
    else:
      view = self._window._set_active_tab(tab, 1, 1)
    GLib.idle_add(view.grab_focus)

  def on_saved_config_file(self, *args):
    self.reload_config()

  def click_regex_reload(self, action, data = None):
    self.reload_config()

  def _get_click_iter(self, view, event):
    """Return the current cursor location based on the click location."""
    buffer_x, buffer_y = view.window_to_buffer_coords(
                    view.get_window_type(event.window),
                    int(event.x),
                    int(event.y))
    event_iter = view.get_iter_at_location(buffer_x, buffer_y)
    return event_iter

  def on_view_button_press_event(self, view, event):
    # handle left double click
    if event.button == 1 and event.type == Gdk.EventType._2BUTTON_PRESS:

      r = re.compile(self.config['double_click'])

      click_iter = self._get_click_iter(view, event)
      if not click_iter:
        click_iter = self._get_insert_iter()

      # find boundaries
      # backward_find_char and forward_find_char would be perfect, but they do not work by now...

      # go to the left until start of line or non-word char is found
      l_iter = click_iter.copy()
      while r.match(l_iter.get_char()) and l_iter.get_line_offset() > 0:
        l_iter.backward_char()
      if not r.match(l_iter.get_char()):
        l_iter.forward_char()

      # go to the right until start of line or non-word char is found
      r_iter = click_iter.copy()
      while r.match(r_iter.get_char()) and r_iter.get_line_offset() > 0:
        r_iter.forward_char()
      if r_iter.get_offset() < l_iter.get_offset():
        l_iter.backward_char()
        r_iter = l_iter.copy()

      doc = self._window.get_active_document()
      doc.select_range(l_iter,r_iter)

      return True

  def get_config_file_path(self):
    return os.path.dirname(os.path.abspath(inspect.getfile(inspect.currentframe()))) + '/config.json'

  def reload_config(self):
    self.config = { 'double_click': '[\w_]' }
    try:
      self.config = json.load( open( self.config_file ) )
    except:
      print( 'click_regex: Could not load config file from ' + str(self.config_file) )
      print( str(sys.exc_info()) )
