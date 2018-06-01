# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.
#
# Copyright (c) 2018, Galen Curwen-McAdams

import hashlib
import uuid
import copy
import io
import os
import subprocess
import argparse
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
    attribute = attr.ib(default="")
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
        self.queue_order = {}
        self.active_fold_thumbnail = None
        super(WipContainer, self).__init__(**kwargs)

    def update(self):
        self.clear_widgets()
        for wip_name, wip in self.wipset.wips.items():
            w = WipItem(wip, height=400, size_hint_y=None)
            try:
                w.wip.queue_position = self.queue_order[w.wip.xml_str_hash]
            except KeyError:
                pass

            self.add_widget(w)
            w.update_actions()
        self.sort_queue()

    def slurp_file_to_image(self, filename, container_widget):
        # print("slurping {} to {}".format(filename, container_widget))
        data = io.BytesIO(open(filename, "rb").read())
        self.active_fold_thumbnail = CoreImage(io.BytesIO(open(filename, "rb").read()), ext="jpg").texture
        container_widget.texture = CoreImage(data, ext="jpg").texture
        # container_widget.size = container_widget.texture_size
        # print("removing thumb {}".format(filename))
        os.remove(filename)

    def sort_queue(self):
        self.clear_widgets()
        queued = {}

        for wip_name, wip in self.wipset.wips.items():
            if not wip.queue_position in queued:
                queued[wip.queue_position] = []
            queued[wip.queue_position].append(wip)
            self.queue_order[wip.xml_str_hash] = wip.queue_position

        order = sorted(queued.keys())
        active = True
        for key_name in order:
            for wip in queued[key_name]:
                w = WipItem(wip, height=400, size_hint_y=None)
                if active is True:
                    w.queue_input.background_color = (0, 1, 0, 1)
                    # try to generate a fold thumbnail
                    # set size to 1x1 so kivy window does not popup
                    thumb_name = "/tmp/thumb_{}.jpg".format(str(uuid.uuid4())).replace("-","")
                    thumb_call = "ma-ui-fold --size=1x1 -- --thumbnail-only --thumbnail-name {} --thumbnail-width 300 --thumbnail-height 300".format(thumb_name)
                    p = subprocess.Popen(thumb_call.split(" "), stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                    print("scheduling call ",active)
                    Clock.schedule_once(lambda dt, w=w: self.slurp_file_to_image(thumb_name, w.image_project_folds), 7)
                    # try to persist fold thumbnail by using previous version...
                    try:
                        w.image_project_folds.texture = self.active_fold_thumbnail#CoreImage(self.active_fold_thumbnail, ext="jpg").texture
                    except Exception as ex:
                        print(ex)

                    active = False
                conditions = []
                for s in self.app.setting_container.settings_container.children:
                    if isinstance(s.item, SetSet):
                        conditions.append(s.item)
                        b = Button(text=str(s.item.conditions), background_normal='', background_color=(*s.item.color.rgb, 1))
                        w.conditions_container.add_widget(b)
                self.add_widget(w)
                w.update_actions()

class WipItem(BoxLayout):
    def __init__(self, wip, **kwargs):
        self.wip = wip
        self.image_project_dimensions = Image()
        self.image_project_overview = Image()
        self.image_project_folds = Image(height=0, width=0)
        self.actions_container = BoxLayout(orientation="horizontal", size_hint_y=None)
        super(WipItem, self).__init__(**kwargs)
        self.queue_input = TextInput(text=str(self.wip.queue_position), size_hint_x=None, multiline=False)
        self.queue_input.bind(on_text_validate=lambda widget: self.update_queue_position())
        self.add_widget(self.queue_input)

        self.add_widget(self.image_project_dimensions)
        self.add_widget(self.image_project_overview)
        self.add_widget(self.image_project_folds)
        self.add_widget(self.actions_container)

        overview = visualizations.project_overview(self.wip.project, 500, 200, orientation='horizontal', color_key=True, background_color=(50, 50, 50, 255))[1]
        self.image_project_overview.texture = CoreImage(overview, ext="jpg", keep_data=True).texture
        self.image_project_overview.size = self.image_project_overview.texture_size
        dimensions = visualizations.project_dimensions(self.wip.project, 500, 150, scale=5, background_color=(50, 50, 50, 255))[1]
        self.image_project_dimensions.texture = CoreImage(dimensions, ext="jpg", keep_data=True).texture
        self.image_project_dimensions.size = self.image_project_dimensions.texture_size
        self.conditions_container = BoxLayout(orientation="horizontal", size_hint_y=None, size_hint_x=None)
        self.add_widget(self.conditions_container)

        self.update_actions()

    def update_queue_position(self):
        try:
            self.wip.queue_position = int(self.queue_input.text)
            self.parent.sort_queue()
        except Exception as ex:
            print(ex)

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
        w.xml_str_hash =  hashlib.sha224(xml.encode()).hexdigest()
        w.xml_str = xml
        xml = etree.fromstring(xml)

        # tree = etree.ElementTree(xml)
        # tree.write('{}.xml'.format(w.xml_str_hash), pretty_print=True)#, xml_declaration=True)

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
    queue_position = attr.ib(default=0)

    def activate(self):
        pass

    def deactivate(self):
        pass

class SetItem(BoxLayout):
    def __init__(self, item, **kwargs):
        self.item = item
        self.item_color_button = Button(text= "", background_normal='', font_size=20)
        self.item_color_button.bind(on_press=self.pick_color)
        if self.item is not None:
            self.item_color_button.background_color = (*self.item.color.rgb, 1)
        self.item_delete_button = Button(text="del", size_hint_x=None)
        self.item_delete_button.bind(on_press=lambda widget: self.remove())
        super(SetItem, self).__init__(**kwargs)
        self.add_widget(self.item_color_button)
        self.item_container = BoxLayout(orientation="horizontal")
        self.add_widget(self.item_container)
        if item is not None:
            self.type_fields()
        else:
            self.configure()

        self.add_widget(self.item_delete_button)

    def configure(self):
        type_dd = self.create_dropdown(["call", "setset"], callback=self.select_type)
        self.add_widget(type_dd)

    def remove(self):
        self.parent.parent.remove_item(self)

    def action(self):
        self.item.action()

    def update_item_field(self, item, field, value, field_widget, split=False):
        if split:
            setattr(item, field, value.split(split))
        else:
            setattr(item, field, value)
        field_widget.text = value
        print(item)
        #field_widget.hint_text = value

    def select_type(self, item_type):
        self.item_container.clear_widgets()
        if item_type == "call":
            self.item = Call()
        if item_type == "setset":
            self.item = SetSet()
        self.item_color_button.background_color = (1, 1, 1, 1)
        self.type_fields()

    def type_fields(self):
        type_widgets = None
        if isinstance(self.item, Call):
            type_widgets = BoxLayout(orientation="horizontal")
            call_input = TextInput(hint_text="call", multiline=False)
            call_input.bind(on_text_validate=lambda widget: self.update_item_field(self.item, "value", widget.text, widget))
            type_widgets.add_widget(call_input)
            args_input = TextInput(hint_text="comma separated args", multiline=False)
            args_input.bind(on_text_validate=lambda widget: self.update_item_field(self.item, "args", widget.text, widget, split=","))

            type_widgets.add_widget(args_input)
        elif isinstance(self.item, SetSet):
            type_widgets = BoxLayout(orientation="horizontal")
            attribute_input = TextInput(hint_text="attribute to set", multiline=False)
            attribute_input.bind(on_text_validate=lambda widget: self.update_item_field(self.item, "attribute", widget.text, widget))
            value_input = TextInput(hint_text="set to value", multiline=False)
            value_input.bind(on_text_validate=lambda widget: self.update_item_field(self.item, "value", widget.text, widget))
            conditions_input = TextInput(hint_text="comma separated conditions", multiline=False)
            conditions_input.bind(on_text_validate=lambda widget: self.update_item_field(self.item, "conditions", widget.text, widget, split=","))
            type_widgets.add_widget(attribute_input)
            type_widgets.add_widget(value_input)
            type_widgets.add_widget(conditions_input)
        if type_widgets is not None:
            self.item_container.add_widget(type_widgets)

    def create_dropdown(self, values, callback=None):
        d = DropDown()
        setattr(self, "dd_" + str(uuid.uuid4()), d)
        d_default = Button(text="")
        d_default.bind(on_release=d.open)
        for value in values:
            btn = Button(text=value, size_hint_y=None, height=44)
            btn.bind(on_release=lambda btn: d.select(btn.text))
            d.add_widget(btn)
        d.bind(on_select=lambda instance, x: self.dropdown_update(instance, x, d_default))
        if callback is not None:
            d.bind(on_select=lambda instance, x: callback(x))

        return d_default

    def dropdown_update(self, widget, selected_value, default, *args):
        default.text = selected_value

    def pick_color(self,*args):
        color_picker = ColorPickerPopup()
        color_picker.content.bind(color=self.on_color)
        color_picker.open()

    def on_color(self, instance, *args):
        # self.item may not exist
        try:
            self.item.color.rgb = instance.color[:3]
            self.item_color_button.background_color = (*self.item.color.rgb, 1)
            self.parent.parent.app.wips_container.update()
        except AttributeError:
            pass

class SettingContainer(BoxLayout):
    def __init__(self, app, **kwargs):
        self.app = app
        self.settings = self.app.settings
        self.settings_container = BoxLayout(orientation="vertical")
        super(SettingContainer, self).__init__(**kwargs)
        self.create_button = Button(text="create", size_hint_x=None)
        self.create_button.bind(on_press=lambda widget: self.create_item())
        self.add_widget(self.settings_container)
        self.add_widget(self.create_button)
        self.update_widgets()

    def update_widgets(self):
        self.settings_container.clear_widgets()
        for widget in self.settings:
            self.settings_container.add_widget(widget)

    def create_item(self):
        w = SetItem(None)
        self.settings_container.add_widget(w)

    def remove_item(self, item):
        self.settings_container.remove_widget(item)
        del item

class QueueApp(App):
    def __init__(self, *args,**kwargs):
        self.queued = {}
        self.wips = WipSet()
        self.settings = []
        self.project_files = []
        if "project_file" in kwargs:
            self.project_files = kwargs["project_file"]
        super(QueueApp, self).__init__()

    def load_xml_files(self):
        for file in self.project_files:
            with open(file, "r") as f:
                self.wips.add(f.read())
                self.wips_container.update()

    def check_for_projects(self):
        try:
            for key in redis_conn.scan_iter("project:*"):
                xml = redis_conn.get(key)
                self.wips.add(xml)
                self.wips_container.update()
        except (redis.exceptions.ConnectionError, TypeError) as ex:
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
                    obj = SetSet(attribute=str(default.xpath("./@attribute")[0]), value=str(default.xpath("./@value")[0]))
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
        self.load_xml_files()
        Clock.schedule_interval(lambda x: self.check_for_projects(), 10)
        return root

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--project-file",
                        nargs='+',
                        default=[],
                        help="project file(s) in xml")
    args = parser.parse_args()
    app = QueueApp(**vars(args))
    app.run()
