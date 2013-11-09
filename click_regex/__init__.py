# -*- coding: utf8 -*-
#  Click Regex plugin for gedit
#
#  Copyright (C) 2013-2013 Rubén Caro
#
#  This program is free software: you can redistribute it and/or modify
#  it under the terms of the GNU General Public License as published by
#  the Free Software Foundation, either version 3 of the License, or
#  (at your option) any later version.
#
#  This program is distributed in the hope that it will be useful,
#  but WITHOUT ANY WARRANTY; without even the implied warranty of
#  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#  GNU General Public License for more details.
#
#  You should have received a copy of the GNU General Public License
#  along with this program.  If not, see <http://www.gnu.org/licenses/>.

from gi.repository import GObject, Gedit, Gtk, Gio, Gdk, GLib
import os, os.path

def spit(obj):
    print( str(obj) )

# essential interface
class ClickRegexPluginInstance:
    def __init__( self, plugin, window ):
        self._window = window
        self._plugin = plugin
        self._insert_menu()

    def deactivate( self ):
        self._remove_menu()
        self._action_group = None
        self._window = None
        self._plugin = None

    def update_ui( self ):
        pass

    # MENU STUFF
    def _insert_menu( self ):
        manager = self._window.get_ui_manager()

        self._action_group = Gtk.ActionGroup( "ClickRegexPluginActions" )
        self._action_group.add_actions([
            ("ConfigureClickRegexAction", Gtk.STOCK_FIND, "Configure click regex...",
             '<Ctrl><Alt>R', "Configure click regex",
             lambda a: self.on_configure_action()),
        ])

        manager.insert_action_group(self._action_group)

        ui_str = """
          <ui>
            <menubar name="MenuBar">
              <menu name="EditMenu" action="Edit">
                <placeholder name="EditOps_7">
                  <menuitem name="ClickRegex" action="ConfigureClickRegexAction"/>
                </placeholder>
              </menu>
            </menubar>
          </ui>
          """

        self._ui_id = manager.add_ui_from_string(ui_str)

    def _remove_menu( self ):
        manager = self._window.get_ui_manager()
        manager.remove_ui( self._ui_id )
        manager.remove_action_group( self._action_group )
        manager.ensure_update()


# STANDARD PLUMMING
class ClickRegexPlugin(GObject.Object, Gedit.WindowActivatable):
    __gtype_name__ = "ClickRegexPlugin"
    DATA_TAG = "ClickRegexPluginInstance"

    window = GObject.property(type=Gedit.Window)

    def __init__(self):
        GObject.Object.__init__(self)

        self._mouse_handler_ids_per_view = {}
        """The mouse handler id for each of the window's views."""

        self._drag_handler_ids_per_view = {}
        """Motion and button-release handlers for drag selecting."""

        self.tab_removed_handler = None
        """Signal handler for a tab being removed from the window."""

        self._last_click = [None, 0, 0, 0, 0, 0]
        """
        The Gtk.TextIter of the most recent click and the times of the most
        recent click for each of the five click types.
        """

        gtk_settings = Gtk.Settings.get_default()
        gtk_doubleclick_ms = gtk_settings.get_property('gtk-double-click-time')
        self._double_click_time = float(gtk_doubleclick_ms)/1000
        """Maximum time between consecutive clicks in a multiple click."""

        # These attributes are used for extending the selection for click-drag.
        self._word_re = None
        """The compiled regular expression object of the current click."""
        self._boundaries = None
        """All start and end positions of matches of the current click."""
        self._click_start_iter = None
        """Start iter of the clicked selection."""
        self._click_end_iter = None
        """End iter of the clicked selection."""

    def _get_instance( self ):
        return self.window.DATA_TAG

    def _set_instance( self, instance ):
        self.window.DATA_TAG = instance

    def do_activate( self ):
        self._set_instance( ClickRegexPluginInstance( self, self.window ) )
        self._connect_window()
        self.do_update_state()

    def do_deactivate( self ):
        if self._get_instance():
            self._get_instance().deactivate()
        self._set_instance( None )

    def do_update_ui( self ):
        self._get_instance().update_ui()

    def _connect_window(self):
        """Connect handler for tab removal."""
        self.tab_removed_handler = self.window.connect('tab-removed',
            self.on_tab_removed)

    def on_tab_removed(self, window, tab):
        self._disconnect_tab(tab)
        return False

    def _connect_tab(self, tab):
        """Connect signal handlers to the View(s) in the tab."""
        scrollwin = self._get_tab_scrollwin(tab)
        for view in self._get_scrollwin_views(scrollwin):
            self._connect_view(view)

    def _disconnect_tab(self, tab):
        """Disconnect signal handlers from the View(s) in the tab."""
        scrollwin = self._get_tab_scrollwin(tab)
        for view in self._get_scrollwin_views(scrollwin):
            self._disconnect_view(view)

    def _connect_view(self, view):
        """Connect the mouse handler to the view."""
        if view not in self._mouse_handler_ids_per_view:
            self._connect_mouse_handler(view)

    def _disconnect_view(self, view):
        """Disconnect the mouse handler from the view."""
        if view in self._mouse_handler_ids_per_view:
            self._disconnect_mouse_handler(view)

    def _connect_mouse_handler(self, view):
        """Connect the handler for the view's button_press_event."""
        self._mouse_handler_ids_per_view[view] = \
            view.connect("button_press_event", self._handle_button_press)

    def _disconnect_mouse_handler(self, view):
        """Disconnect the handler for the view's button_press_event."""
        handler_id = self._mouse_handler_ids_per_view.pop(view)
        if view.handler_is_connected(handler_id):
            view.disconnect(handler_id)

    def _handle_button_press(self, view, event):
        """
        Evaluate mouse click and call for text selection as appropriate.
        Return False if the click should still be handled afterwards.
        """
        handled = False
        if event.button == 1:
            click_iter = self._get_click_iter(view, event)
            now = time.time()
            handlers_by_type = {
                Gdk.EventType.BUTTON_PRESS: self._handle_1button_press,
                Gdk.EventType._2BUTTON_PRESS: self._handle_2button_press,
                Gdk.EventType._3BUTTON_PRESS: self._handle_3button_press,
                }
            handled, click = handlers_by_type[event.type](click_iter, now)
            if click:
                handled = self._make_assigned_selection(click, click_iter)
        return handled

    def _handle_button_release(self, widget, event):
        """Handle left mouse button being released."""
        if event.button == 1:
            self._disconnect_drag_handler(widget)
        return False

    def _handle_1button_press(self, click_iter, now):
        """Detect 5-click, 4-click, or 1-click. Otherwise eat the signal."""
        handled = False
        click = None
        if self._last_click[0] and click_iter.equal(self._last_click[0]):
            # The pointer must remain in the same position as the first click,
            # for it to be considered a successive click of a multiple click.
            if now - self._last_click[4] < self._double_click_time:
                # QUINTUPLE-CLICKS are handled here.
                self._last_click[5] = now
                click = 5
            elif now - self._last_click[3] < self._double_click_time:
                # QUADRUPLE-CLICKS are handled here.
                self._last_click[4] = now
                click = 4
            elif now - self._last_click[2] < self._double_click_time:
                # Ignore and consume it.  Triple-clicks are not handled here.
                handled = True
            elif now - self._last_click[1] < self._double_click_time:
                # Ignore and consume it.  Double-clicks are not handled here.
                handled = True
        if not handled and not click:
            # SINGLE-CLICKS are handled here.
            # Record this as the original click.
            self._last_click = [click_iter, now, 0, 0, 0, 0]
            click = 1
        return handled, click

    def _handle_2button_press(self, click_iter, now):
        """Detect 2-click. Otherwise eat the signal."""
        handled = False
        click = None
        if self._last_click[0] and click_iter.equal(self._last_click[0]):
            if (now - self._last_click[4]) < self._double_click_time:
                # Ignore and consume it.  Quintuple-clicks are not handled here.
                handled = True
            else:
                # DOUBLE-CLICKS are handled here.
                self._last_click[2] = now
                click = 2
        return handled, click

    def _handle_3button_press(self, click_iter, now):
        """Detect 3-click. Otherwise eat the signal."""
        handled = False
        click = None
        if self._last_click[0] and click_iter.equal(self._last_click[0]):
            if (now - self._last_click[5]) < self._double_click_time:
                # Ignore and consume it.  Sextuple-clicks are not handled here.
                handled = True
            else:
                # TRIPLE-CLICKS are handled here.
                self._last_click[3] = now
                click = 3
        return handled, click

    def _make_assigned_selection(self, click, click_iter):
        """Select text based on the click type and location."""
        acted = False
        # TODO: actually do something and set acted = True
#        op = self._plugin.conf.get_op(click=click)
#        if op.name != 'None':
#            acted = self._select_op(op, click_iter=click_iter)
        return acted

    def _get_click_iter(self, view, event):
        """Return the current cursor location based on the click location."""
        buffer_x, buffer_y = view.window_to_buffer_coords(
                        view.get_window_type(event.window),
                        int(event.x),
                        int(event.y))
        event_iter = view.get_iter_at_location(buffer_x, buffer_y)
        return event_iter

    def _get_tab_scrollwin(self, tab):
        """Return the ScrolledWindow of the tab."""
        view_frame = tab.get_children()[0]
        animated_overlay = view_frame.get_children()[0]
        scrollwin = animated_overlay.get_children()[0]
        return scrollwin

    def _get_scrollwin_views(self, scrollwin):
        """Return the View(s) in the ScrolledWindow."""
        child = scrollwin.get_child()
        return [child]

    def _disconnect_drag_handler(self, view):
        """Disconnect the event handlers for drag selecting."""
        handler_ids = self._drag_handler_ids_per_view.pop(view)
        for handler_id in handler_ids:
            if view.handler_is_connected(handler_id):
                view.disconnect(handler_id)
        # Clear the match data of the click.
        self._word_re = None
        self._boundaries = None
        self._click_start_iter = None
        self._click_end_iter = None

    def get_doc_language(self):
        """Return the programming language of the current document."""
        doc = self.window.get_active_document()
        doc_language = doc.get_language()
        if doc_language:
            doc_language_name = doc_language.get_name()
        else:
            doc_language_name = '-None-'
        return doc_language_name

    def do_update_state(self):
        """
        Identify the document and connect the menu and mouse handling.

        A mouse handler connection must be made for each view.
        """
        doc = self.window.get_active_document()
        view = self.window.get_active_view()
        tab = self.window.get_active_tab()
        if doc and view and view.get_editable():
            self._connect_tab(tab)

    #################################3
    # Text selection functions:

    def _select_op(self, op, click_iter=None):
        """Finds first regex match that includes the click position."""

        char_spec = op.pattern
        flags = op.flags

        if not click_iter:
            click_iter = self._get_insert_iter()

        word_re = re.compile(char_spec, flags)

        did_select = self._select_regex(click_iter, word_re)
        return did_select

    def _select_regex(self, click_iter, word_re, extend=False):
        """
        Select text in the document matching word_re and containing click_iter.
        """
        if not extend:
            self._word_re = word_re

        doc = self.window.get_active_document()

        multiline = bool(word_re.flags & re.M)
        if multiline:
            if not extend:
                source_start_iter, source_end_iter = doc.get_bounds()
            pick_pos = click_iter.get_offset()
        else:
            source_start_iter, source_end_iter = \
                self._get_line_iter_pair(click_iter)
            pick_pos = click_iter.get_line_offset()

        if extend and multiline:
            source_text = None
        else:
            source_text = source_start_iter.get_slice(source_end_iter)
            #FIXME: Update the whole plugin properly for Unicode.
            encoding = doc.get_encoding().get_charset()
            source_text = unicode(source_text, encoding)
            if source_text == '':
                return False

        match_start, match_end = self._find_text(source_text, pick_pos, word_re)
        target_start_iter = click_iter.copy()
        target_end_iter = click_iter.copy()
        if multiline:
            target_start_iter.set_offset(match_start)
            target_end_iter.set_offset(match_end)
        else:
            target_start_iter.set_line_offset(match_start)
            target_end_iter.set_line_offset(match_end)

        if extend:
            target_start_iter = min((self._click_start_iter,
                                    target_start_iter),
                                    key=lambda i: i.get_offset())
            #extended_back = target_start_iter != self._click_start_iter
            target_end_iter = max((self._click_end_iter,
                                  target_end_iter),
                                  key=lambda i: i.get_offset())
            #extended_forward = target_end_iter != self._click_end_iter
        else:
            self._click_start_iter = target_start_iter
            self._click_end_iter = target_end_iter

        current_selection_bounds = doc.get_selection_bounds()
        if current_selection_bounds:
            current_start_iter, current_end_iter = current_selection_bounds
            if (current_start_iter.equal(target_start_iter) and
                    current_end_iter.equal(target_end_iter)):
                # The text is already selected; there's no need to re-select it.
                return True
        doc.select_range(target_start_iter, target_end_iter)
        selected_text = doc.get_text(target_start_iter, target_end_iter, False)
        # These two lines will activate search highlighting on the text:
#        found_text = doc.get_text(target_start_iter, target_end_iter)
#        doc.set_search_text(found_text, 1)
        return True

    def _find_text(self, source_text, pick_pos, word_re):
        """
        Finds the range of the match, or the range between matches, for regex
        word_re within source_text that includes the position pick_pos.
        If there is no match, then the whole document is selected as being
        between matches.
        """
        # self._boundaries is set by a multiline click selection,
        # remains available for a multiline click-drag selection,
        # and then is set to None by self._disconnect_drag_handler().
        boundaries = self._boundaries
        if not boundaries:
            boundaries = self._find_boundaries(source_text, word_re)

        after = next((p for p in boundaries if p > pick_pos), boundaries[-1])
        after_index = boundaries.index(after)
        before = boundaries[after_index - 1]

        # For single-line regexes, the boundaries
        # need to be determined each time.
        if word_re.flags & re.M:
            self._boundaries = boundaries

        return before, after

    def _find_boundaries(self, source_text, word_re):
        """Find the offsets of all match starting and ending positions."""

        spans = ((m.start(), m.end()) for m in word_re.finditer(source_text))
        boundaries = list(itertools.chain.from_iterable(spans))

        source_start = 0
        source_end = len(source_text)

        if boundaries:
            if boundaries[0] != source_start:
                boundaries.insert(0, source_start)
            if boundaries[-1] != source_end:
                boundaries.append(source_end)
        else:
            boundaries = [source_start, source_end]

        return boundaries

    def _get_line_iter_pair(self, a_text_iter):
        """Return iters for the start and end of this iter's line."""
        left_iter = a_text_iter.copy()
        right_iter = a_text_iter.copy()
        left_iter.set_line_offset(0)
        if not right_iter.ends_line():
            right_iter.forward_to_line_end()
        return left_iter, right_iter
