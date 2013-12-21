# -*- encoding:utf-8 -*-

from gi.repository import GObject, Gtk, Gedit, PeasGtk

from .click_regex import ClickRegexWindowHelper

class ClickRegexPlugin(GObject.Object, Gedit.WindowActivatable):
	__gtype_name__ = "ClickRegexPlugin"
	window = GObject.property(type=Gedit.Window)

	def __init__(self):
		GObject.Object.__init__(self)

	def do_activate(self):
		self._plugin = ClickRegexWindowHelper(self, self.window)

	def do_deactivate(self):
		self._plugin.deactivate()
		del self._plugin

	def do_update_state(self):
		self._plugin.update_ui()

	def get_instance(self):
		return self._plugin, self.window
