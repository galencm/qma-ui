# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.
#
# Copyright (c) 2018, Galen Curwen-McAdams

import hashlib
import uuid
import redis
import attr
from lxml import etree
from kivy.app import App
from kivy.lang import Builder
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.scrollview import ScrollView
from kivy.uix.label import Label
from kivy.uix.image import Image
from kivy.uix.tabbedpanel import TabbedPanel, TabbedPanelItem
from kivy.core.image import Image as CoreImage
from kivy.clock import Clock
from ma_cli import data_models
from ma_wip import visualizations
from ma_wip.ling_classes import Rule, Group, Category

try:
    r_ip, r_port = data_models.service_connection()
    binary_r = redis.StrictRedis(host=r_ip, port=r_port)
    redis_conn = redis.StrictRedis(host=r_ip, port=r_port, decode_responses=True)
except redis.exceptions.ConnectionError:
    pass


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

class WipItem(BoxLayout):
    def __init__(self, wip, **kwargs):
        self.wip = wip
        self.image_project_dimensions = Image()
        self.image_project_overview = Image()
        super(WipItem, self).__init__(**kwargs)
        self.add_widget(self.image_project_dimensions)
        self.add_widget(self.image_project_overview)
        #self.add_widget(Label(text=str(self.wip.project)))
        overview = visualizations.project_overview(self.wip.project, 500, 200, orientation='horizontal', color_key=True, background_color=(50, 50, 50, 255))[1]
        self.image_project_overview.texture = CoreImage(overview, ext="jpg", keep_data=True).texture

        dimensions = visualizations.project_dimensions(self.wip.project, 500, 150, scale=5, background_color=(50, 50, 50, 255))[1]
        self.image_project_dimensions.texture = CoreImage(dimensions, ext="jpg", keep_data=True).texture

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
    # a pipe?
    fold_ui = attr.ib(default=None)

    def rules_activate(self):
        pass

    def rules_deactivate(self):
        pass

    def settings_activate(self):
        pass

    def settings_deactivate(self):
        pass

    def configure_ui(self):
        # starts / restarts / updates lattice-ui
        # palette, expected, etc...
        pass

class SettingsContainer(BoxLayout):
    def __init__(self, app, **kwargs):
        self.app = app
        super(SettingsContainer, self).__init__(**kwargs)

    # launcher

class QueueApp(App):
    def __init__(self, *args,**kwargs):
        self.queued = {}
        self.wips = WipSet()
        super(QueueApp, self).__init__()

    def check_for_projects(self):
        try:
            for key in redis_conn.scan_iter("project:*"):
                xml = redis_conn.get(key)
                self.wips.add(xml)
                self.wips_container.update()
        except redis.exceptions.ConnectionError:
            pass

    def build(self):
        root = BoxLayout()
        root = TabbedPanel(do_default_tab=False)
        root.tab_width = 200

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
        tab.add_widget(SettingsContainer(self))
        root.add_widget(tab)

        self.check_for_projects()
        Clock.schedule_interval(lambda x: self.check_for_projects(), 10)
        return root

if __name__ == "__main__":
    app = QueueApp()
    app.run()
