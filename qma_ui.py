# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.
#
# Copyright (c) 2018, Galen Curwen-McAdams

import hashlib
import uuid
import copy
import subprocess
import redis
import attr
from lxml import etree
from kivy.app import App
from kivy.lang import Builder
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.scrollview import ScrollView
from kivy.uix.label import Label
from kivy.uix.image import Image
from kivy.uix.button import Button
from kivy.uix.textinput import TextInput
from kivy.uix.tabbedpanel import TabbedPanel, TabbedPanelItem
from kivy.uix.colorpicker import ColorPicker
from kivy.uix.dropdown import DropDown
from kivy.uix.popup import Popup
from kivy.core.image import Image as CoreImage
from kivy.clock import Clock
import colour
from ma_cli import data_models
from ma_wip import visualizations
from ma_wip.ling_classes import Rule, Group, Category

try:
    r_ip, r_port = data_models.service_connection()
    binary_r = redis.StrictRedis(host=r_ip, port=r_port)
    redis_conn = redis.StrictRedis(host=r_ip, port=r_port, decode_responses=True)
except redis.exceptions.ConnectionError:
    pass

@attr.s
class Call(object):
    value = attr.ib(default="")
    args = attr.ib(default=attr.Factory(list))
    color = attr.ib(default=None)

    @color.validator
    def check(self, attribute, value):
        if value is None:
            setattr(self,'color', colour.Color(pick_for=self))

    def action(self):
        try:
            subprocess.Popen([self.value, *[arg for arg in self.args if arg]])
        except FileNotFoundError:
            print(self, self.value)

@attr.s
class SetSet(object):
    value = attr.ib(default="")
    set_to = attr.ib(default="")
    conditions = attr.ib(default=attr.Factory(list))
    color = attr.ib(default=None)

    @color.validator
    def check(self, attribute, value):
        if value is None:
            setattr(self,'color', colour.Color(pick_for=self))

class ColorPickerPopup(Popup):
    def __init__(self, **kwargs):
        self.title = "foo"
        self.content = ColorPicker()
        self.size_hint = (.5,.5)
        super(ColorPickerPopup, self).__init__()

class WipContainer(BoxLayout):
    def __init__(self, app, wipset, **kwargs):
        self.app = app
        self.wipset = wipset
        super(WipContainer, self).__init__(**kwargs)

    def update(self):
        self.clear_widgets()
        for wip_name, wip in self.wipset.wips.items():
            w = WipItem(wip, height=400, size_hint_y=None)
            self.add_widget(w)
            w.update_actions()

class WipItem(BoxLayout):
    def __init__(self, wip, **kwargs):
        self.wip = wip
        self.image_project_dimensions = Image()
        self.image_project_overview = Image()
        self.actions_container = BoxLayout(orientation="vertical")
        super(WipItem, self).__init__(**kwargs)
        #self.actions_container.add_widget(Label(text=str(self.wip.project)))
        self.add_widget(self.image_project_dimensions)
        self.add_widget(self.image_project_overview)
        self.add_widget(self.actions_container)
        overview = visualizations.project_overview(self.wip.project, 500, 200, orientation='horizontal', color_key=True, background_color=(50, 50, 50, 255))[1]
        self.image_project_overview.texture = CoreImage(overview, ext="jpg", keep_data=True).texture

        dimensions = visualizations.project_dimensions(self.wip.project, 500, 150, scale=5, background_color=(50, 50, 50, 255))[1]
        self.image_project_dimensions.texture = CoreImage(dimensions, ext="jpg", keep_data=True).texture
        self.update_actions()

    def update_actions(self):
        self.actions_container.clear_widgets()
        try:
            for action in self.parent.app.settings:
                print(action)
                if isinstance(action.item, Call):
                    btn = None
                    btn = Button(text=action.item.value, size_hint_x=None, size_hint_y=None, height=44)
                    btn.background_normal = ''
                    btn.background_color = (*action.item.color.rgb, 1)
                    # bind action item for lambda using item=
                    f = lambda widget, item=action.item: item.action()
                    btn.bind(on_press = f)
                    self.actions_container.add_widget(btn)
        except AttributeError as ex:
            print(ex)
            pass

@attr.s
class WipSet(object):
    wips = attr.ib(default=attr.Factory(dict))

    def add(self, xml):
        xml_hash =  hashlib.sha224(xml.encode()).hexdigest()
        self.wips[xml_hash] = self.load_project_xml(xml)

    def load_project_xml(self, xml):
        w = Wip()
        project_xml = {}
        xml = etree.fromstring(xml)
        w.project['categories'] = {}
        w.project['palette'] = {}
        w.project['order'] = {}


        for project in xml.xpath('//project'):
            for attribute in project.attrib:
                project_xml[attribute] = project.get(attribute)
            w.project.update(project_xml)

            for rule in project.xpath('//rule'):
                r = Rule()
                r.source_field = str(rule.xpath("./@source")[0])
                r.dest_field = str(rule.xpath("./@destination")[0])
                r.rule_result = str(rule.xpath("./@result")[0])
                # does not handle multiple parameters
                for parameter in rule.xpath('//parameter'):
                    r.comparator_symbol = str(parameter.xpath("./@symbol")[0])
                    r.comparator_params = [str(parameter.xpath("./@values")[0])]
                w.rules.append(r)

            for category in project.xpath('//category'):
                try:
                    rough_order = float(category.xpath("./@rough_order")[0])
                except:
                    rough_order = 0
                c = Category(name = str(category.xpath("./@name")[0]),
                             color = str(category.xpath("./@color")[0]),
                             rough_amount = int(category.xpath("./@rough_amount")[0]),
                             rough_order = rough_order)
                try:
                    c.rough_amount_start = category.xpath("./@rough_amount_start")[0]
                    c.rough_amount_end = category.xpath("./@rough_amount_end")[0]
                except Exception as ex:
                    pass
                w.categories.append(c)
                w.project['categories'][c.name] = c.rough_amount
                w.project['palette'][c.name] = {"fill" : c.color}
                w.project['order'][c.name] = c.rough_order

        return w

@attr.s
class Wip(object):
    xml = attr.ib(default="")
    xml_str = attr.ib(default="")
    xml_str_hash = attr.ib(default="")
    project = attr.ib(default=attr.Factory(dict))
    rules = attr.ib(default=attr.Factory(list))
    categories = attr.ib(default=attr.Factory(list))

    def activate(self):
        pass

    def deactivate(self):
        pass

class SetItem(BoxLayout):
    def __init__(self, item, **kwargs):
        self.item = item
        self.item_color_button = Button(text= "", background_normal='', font_size=20)
        self.item_color_button.bind(on_press=self.pick_color)
        self.item_color_button.background_color = (*self.item.color.rgb, 1)
        super(SetItem, self).__init__(**kwargs)
        self.add_widget(self.item_color_button)
        self.event_type_dd = self.create_dropdown(["activate","deactivate"])
        self.add_widget(self.event_type_dd)

    def action(self):
        self.item.action()

    def create_dropdown(self, values):
        d = DropDown()
        setattr(self, "dd_" + str(uuid.uuid4()), d)
        d_default = Button(text="")
        d_default.bind(on_release=d.open)
        for value in values:
            btn = Button(text=value, size_hint_y=None, height=44)
            btn.bind(on_release=lambda btn: d.select(btn.text))
            d.add_widget(btn)
        d.bind(on_select=lambda instance, x: self.dropdown_update(instance, x, d_default))
        return d_default

    def dropdown_update(self, widget, selected_value, default, *args):
        default.text = selected_value

    def pick_color(self,*args):
        color_picker = ColorPickerPopup()
        color_picker.content.bind(color=self.on_color)
        color_picker.open()

    def on_color(self, instance, *args):
        self.item.color.rgb = instance.color[:3]
        self.item_color_button.background_color = (*self.item.color.rgb, 1)
        self.parent.parent.app.wips_container.update()

    def set_type(self):
        pass

class SettingContainer(BoxLayout):
    def __init__(self, app, **kwargs):
        self.app = app
        self.settings = self.app.settings
        self.settings_container = BoxLayout(orientation="vertical")
        super(SettingContainer, self).__init__(**kwargs)
        self.create_button = Button(text="create")
        self.create_button.bind(on_press=lambda widget: self.create_item())
        self.add_widget(self.settings_container)
        self.add_widget(self.create_button)
        self.update_widgets()

    def update_widgets(self):
        self.settings_container.clear_widgets()
        for widget in self.settings:
            self.settings_container.add_widget(widget)

    def create_item(self):
        pass

class QueueApp(App):
    def __init__(self, *args,**kwargs):
        self.queued = {}
        self.wips = WipSet()
        self.settings = []
        super(QueueApp, self).__init__()

    def check_for_projects(self):
        try:
            for key in redis_conn.scan_iter("project:*"):
                xml = redis_conn.get(key)
                self.wips.add(xml)
                self.wips_container.update()
        except redis.exceptions.ConnectionError:
            pass

    def load(self, file):
        try:
            xml = etree.parse(file)
            for default in xml.xpath('//default'):
                default_type = str(default.xpath("./@type")[0])
                obj = None
                obj_widget = None
                if default_type == "call":
                    obj = Call(value=str(default.xpath("./@value")[0]))
                    for param in default.xpath('//parameter'):
                        if str(param.xpath("./@type")[0]) == "arg":
                            obj.args.append(str(param.xpath("./@value")[0]))
                    obj_widget = SetItem(obj)
                    obj_widget.item = obj
                elif default_type == "setset":
                    obj = SetSet(set_to=str(default.xpath("./@value")[0]), value=str(default.xpath("./@value")[0]))
                    for param in default.xpath('//parameter'):
                        if str(param.xpath("./@type")[0]) == "condition":
                            obj.conditions.append("*")
                    obj_widget = SetItem(obj)
                    obj_widget.item = obj

                if obj_widget:
                    self.settings.append(obj_widget)
        except OSError:
            pass

    def save(self):
        pass

    def build(self):
        root = BoxLayout()
        root = TabbedPanel(do_default_tab=False)
        root.tab_width = 200
        self.load("default.xml")

        self.wips_container = WipContainer(self,
                                           self.wips,
                                           orientation="vertical",
                                           size_hint_y=None,
                                           height=1200,
                                           minimum_height=200)
        queue_scroll = ScrollView(bar_width=20)
        queue_scroll.add_widget(self.wips_container)

        tab = TabbedPanelItem(text="queue")
        tab.add_widget(queue_scroll)
        root.add_widget(tab)

        tab = TabbedPanelItem(text="settings")
        self.setting_container = SettingContainer(self)
        tab.add_widget(self.setting_container)
        self.setting_container.update_widgets()
        root.add_widget(tab)

        self.check_for_projects()
        Clock.schedule_interval(lambda x: self.check_for_projects(), 10)
        return root

if __name__ == "__main__":
    app = QueueApp()
    app.run()
