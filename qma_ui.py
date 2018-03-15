# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.
#
# Copyright (c) 2018, Galen Curwen-McAdams

import redis
from kivy.app import App
from kivy.lang import Builder
from kivy.uix.boxlayout import BoxLayout
from ma_cli import data_models
from ma_wip import visualizations

r_ip, r_port = data_models.service_connection()
binary_r = redis.StrictRedis(host=r_ip, port=r_port)
r = redis.StrictRedis(host=r_ip, port=r_port, decode_responses=True)

class QueueApp(App):
    def __init__(self, *args,**kwargs):
        super(QueueApp, self).__init__()

    def build(self):
        root = BoxLayout()
        return root

if __name__ == "__main__":
    app = QueueApp()
    app.run()
