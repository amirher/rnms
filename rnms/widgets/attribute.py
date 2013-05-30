# -*- coding: utf-8 -*-
#
# This file is part of the Rosenberg NMS
#
# Copyright (C) 2012 Craig Small <csmall@enc.com.au>
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License along
# with this program; if not, see <http://www.gnu.org/licenses/>
#
from tg import url, flash

from sqlalchemy import and_, asc, func

from tw2.jqplugins.jqgrid import jqGridWidget
from tw2.jqplugins.jqplot import JQPlotWidget
from tw2.jqplugins.jqplot.base import pieRenderer_js
import tw2.core as twc

from rnms.model import Attribute, DBSession, Host, EventState, Event
from rnms.lib import states, structures
from rnms.lib.table import jqGridTableBase

from rnms.widgets.base import MapWidget

class AttributeMap(MapWidget):
    id = 'attribute-map'
    host_id = None
    alarmed_only = False

    state_data = twc.Param()

    def attribute_state(self, attribute):
        """ Returns the attribute state which is used for seveity class
        and description box. Returns
        (class,textual)
        """
        if attribute.admin_state == states.STATE_DOWN:
            return ('asd','Admin Down')
        else:
            alarm = Event.attribute_alarm(attribute.id)
            if alarm is None:
                return ('ok', 'Up')
            else:
                return (alarm.event_type.severity_id, alarm.alarm_state.display_name.capitalize())

    def prepare(self):
        conditions = []
        if self.host_id is not None:
            conditions.append(Attribute.host_id == self.host_id)
        if self.alarmed_only == True:
            conditions.append(Attribute.state.internal_state != states.STATE_UP)
        attributes = DBSession.query(Attribute).join(Host,EventState).\
                filter(and_(*conditions)).\
                order_by(asc(Host.display_name), asc(Attribute.display_name))
        if attributes.count() == 0:
            flash('No Attributes Found','alert')
            self.map_groups = None
        else:
            for attribute in attributes:
                astate,state_desc = self.attribute_state(attribute)

                try:
                    atype = attribute.attribute_type.display_name
                except AttributeError:
                    atype = 'Unknown'
                att_fields = [ ('Host', attribute.host.display_name),
                               ('Type', atype),
                               ('Status', state_desc),]
                for k,v in attribute.description_dict().items():
                    if v!= '':
                        att_fields.append((k,v))
                self.add_item(attribute.host_id, attribute.host.display_name,
                              [('Address', attribute.host.mgmt_address)],
                              {'name': attribute.display_name,
                               'state': astate,
                               'url': url('/attributes/'+str(attribute.id)),
                               'fields': att_fields,
                              })
        super(AttributeMap,self).prepare()


class MiniAttributesGrid(structures.attribute_mini, jqGridTableBase):
    __entity__ = Attribute
    __grid_id__ = 'mini-attributes-grid'
    __url__ = '/attributes/minigriddata'
    __hide_primary_field__ = True
    __omit_fields__ = ('__actions__',)
    __caption__ = 'Attributes'
    __height__ = 190
    __scroll__ = True

class AttributesGrid(structures.attribute, jqGridTableBase):
    __grid_id__ = 'attributes-grid'
    __url__ = '/attributes/griddata'
    __omit_fields__ = ('__actions__',)
    __caption__ = 'Attributes'

class DiscoveredAttsGrid(jqGridWidget):
    id = 'discovered-atts-grid'
    host_id = None
    options = {
        'datatype':     'json',
        'autowidth':    True,
        'imgpath':      'scripts/jqGrid/themes/green/images',
        'url':          '/hosts/griddiscover',
        'caption':      'Discovered Attributes',
        'colNames': ('Actions', 'Type', 'Index', 'Name',
                     'State','Description'),
        'colModel': [
            {
                'name': '__actions__', 'align': 'center','width':30,
            },{
                'name': 'attribute_type',
                'id': 'attribute_type',
            },{
                'name': 'index',
                'id': 'index',
                'width': 55,
            },{
                'name': 'display_name',
                'id': 'display_name',
                'width': 100,
            },{
                'name': 'state',
                'id': 'state',
                'width': 30,
            }, {
                'name': 'description',
                'id': 'description',
                'width': 100,
            },
        ],
        'viewrecords':True,
        'grouping' : True,
        'groupingView' : {
            'groupText': ['<b>{0}</b>'],
            'groupField' : ['attribute_type',],
            'groupOrder': ['asc' ],
            'groupColumnShow': False,
        },

    }

    def prepare(self):
        self.options['url'] += '?h={}'.format(self.host_id)
        super(DiscoveredAttsGrid, self).prepare()






class AttributeSummary(twc.Widget):

    id = 'attribute-summary'
    template = 'rnms.templates.widgets.attribute_summary'

    host_id = twc.Param('Limit Attributes by this host id')

    def prepare(self):
        self.url = url
        hostid_filter=[]
        if self.host_id is not None:
            hostid_filter = [Attribute.host_id == self.host_id]

        admin_down = DBSession.query(func.count(Attribute.id)).filter(and_(*(hostid_filter + [Attribute.admin_state == states.STATE_DOWN]))).first()
        self.att_total = int(admin_down[0])
        db_states = DBSession.query(
            EventState.internal_state, func.count(Attribute.id)).\
                join(Attribute).filter(and_(
                    *(hostid_filter + [Attribute.admin_state != states.STATE_DOWN]))).\
                group_by(EventState.internal_state)
        tmp_states = {}
        for att in db_states:
            tmp_states[att[0]] = att[1]
            self.att_total += att[1]

        self.att_states = []
        for state_val,label in states.STATE_NAMES.items():
            if state_val is None:
                self.att_states.append((label,admin_down[0]))
            else:
                try:
                    self.att_states.append((label,tmp_states[state_val]))
                except KeyError:
                    self.att_states.append((label, 0 ))
        super(AttributeSummary, self).prepare()

class oldAttributesGrid(jqGridWidget):
    id ='attribute-grid-id'
    host_id = None
    pager_options = { "search" : True, "refresh" : True, "add" : False,
                     "edit": False, "del": False }
    options = {
            'pager' : 'attribute-grid-pager',
            'datatype': 'json',
            'colNames' : ['Host', 'Name', 'Type', 'Description', 'Oper', 'Admin'],
            'colModel' : [
                {
                    'name' : 'host',
                    'width': 100,
                }, {
                    'name' : 'display_name',
                    'width': 100,
                } , {
                    'name' : 'attribute_type',
                    'width': 100,
                } , {
                    'description' : 'description',
                    'width' : 200,
                } , {
                    'name' : 'oper_state',
                    'width': 60,
                },{
                    'name' : 'admin_state',
                    'width': 60,
                },],
            'rowNum': 15,
            'rowList': [15,30,50],
            'viewrecords': True,
            'imgpath': 'scripts/jqGrid/themes/green/images',
            'height': 'auto',
            }

    def __init__(self):
        # required to reset it
        self.options['url'] = '/attributes/griddata'
        super(AttributesGrid, self).__init__()

    def prepare(self, **kw):
        url_fields = []
        if self.host_id is not None:
            url_fields.append('h={}'.format(self.host_id))

        if url_fields != []:
            self.options['url'] += '?' + '&'.join(url_fields)
        super(AttributesGrid, self).prepare()


class AttributeStatusPie(JQPlotWidget):
    """
    Pie Chart of the Attributes' Status """
    id = 'attribute-status-pie'
    width = "100%"

    resources = JQPlotWidget.resources + [
            pieRenderer_js,
            ]

    options = {
            'seriesColors': [ "#468847", "#F89406", "#B94A48", "#999999", "#3887AD", "#222222"],
            'seriesDefaults' : {
                'renderer': twc.js_symbol('$.jqplot.PieRenderer'),
                'rendererOptions': {
                    'showDataLabels': True,
                    'dataLabels': 'value',
                    },
                },
            'legend': {
                'show': True,
                'location': 'e',
                },
            'grid': {
                'background': '#ffffff',
                'borderColor': '#ffffff',
                'shadow': False,
                },
            }

    def __init__(self, **kwargs):
        super(AttributeStatusPie, self).__init__(**kwargs)
        self.state_list = (states.STATE_UP, states.STATE_ALERT, states.STATE_DOWN, states.STATE_ADMIN_DOWN, states.STATE_TESTING, states.STATE_UNKNOWN)
                
    def prepare(self):
        series = []
        if self.state_data is not None:
            for state in self.state_list:
                try:
                    series.append((states.STATE_NAMES[state].capitalize(), self.state_data[state]))
                except KeyError:
                    series.append((states.STATE_NAMES[state].capitalize(),0))
        self.data = [ series ]
        super(AttributeStatusPie, self).prepare()



