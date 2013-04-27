# -*- coding: utf-8 -*-

"""Setup the Rosenberg-NMS application"""

import logging
import re
import transaction
from sqlalchemy.sql import not_
from sqlalchemy.exc import IntegrityError

from rnms import model
from rnms.websetup import database_data
from rnms.model.graph_type import GraphTypeLineError

logger  = logging.getLogger('rnms')

def bootstrap(command, conf, vars):
    """Place any commands to setup rnms here"""

    # <websetup.bootstrap.before.auth
    try:
        u = model.User()
        u.user_name = u'manager'
        u.display_name = u'Example manager'
        u.email_address = u'manager@somedomain.com'
        u.password = u'managepass'

        model.DBSession.add(u)

        g = model.Group()
        g.group_name = u'managers'
        g.display_name = u'Managers Group'

        g.users.append(u)
    
        model.DBSession.add(g)

        p = model.Permission()
        p.permission_name = u'manage'
        p.description = u'This permission give an administrative right to the bearer'
        p.groups.append(g)

        model.DBSession.add(p)

        u1 = model.User()
        u1.user_name = u'customer'
        u1.display_name = u'Default Customer'
        u1.email_address = u'customer@somedomain.com'
        u1.password = u'customer'

        model.DBSession.add(u1)
        model.DBSession.flush()
        transaction.commit()
    except IntegrityError:
        print 'Warning, there was a problem adding your auth data, it may have already been added:'
        import traceback
        print traceback.format_exc()
        transaction.abort()
        print 'Continuing with bootstrapping...'

    b = BootStrapper()
    b.create()
    b.validate()
    try:

        # SNMP Enterprises
        for ent in database_data.snmp_enterprises:
            e = model.SNMPEnterprise(ent[0], ent[1], ent[2])
            for device in ent[3]:
                d = model.SNMPDevice(e,device[0],device[1])
                model.DBSession.add(d)
            model.DBSession.add(e)
        model.DBSession.flush()
        transaction.commit()
    except IntegrityError:
        print 'Warning, there was a problem adding your base data'
        import traceback
        print traceback.format_exc()
        transaction.abort()

    # <websetup.bootstrap.after.auth>
class BootStrapper(object):
    models = ('defaults', 'autodiscovery', 'alarm_states', 'config_transfers',
            'severities', 'event_types',
            'logmatches', 'snmp_communities',
            'attribute_types', 'graph_types', 'slas',
            'pollers', 'backends', 'poller_sets', 'triggers'

            )

    def __init__(self):
        self.atype_refs = {}
        self.used_event_types = []
        self.used_sla_conditions = []

    def _commit(self, msg):
        try:
            model.DBSession.flush()
            transaction.commit()
        except IntegrityError as errmsg:
            transaction.abort()
            logger.error('Problem creating %s: %s', msg, errmsg)
            #import traceback
            #print traceback.format_exc()
            exit()

    def create(self):
        for m in self.models:
            func = getattr(self, 'create_{}'.format(m))
            func()
            self._commit(m)

        # Some foreign key fixes
        self.fix_attribute_types()

    def validate(self):
        print "\n\n------------------------------------------------------------------------\n"
        print "Validation of data"
        print "Unused Event Types: {0}".format(', '.join([ et.display_name for et in model.DBSession.query(model.EventType).filter(not_(model.EventType.id.in_(self.used_event_types))).all()]))

    def create_defaults(self):
        """
        Any objects that require a specific ID, such as Default Hosts or Admin
        Event types need to be defined here
        """
        zone = model.Zone(u'Default Zone',u'default')
        model.DBSession.add(zone)

        host = model.Host('0.0.0.0','No Host')
        host.zone = zone
        model.DBSession.add(host)

        sla = model.Sla()
        sla.display_name = u'No SLA'
        model.DBSession.add(sla)

        gt = model.GraphType()
        gt.display_name = u'No Graph'
        model.DBSession.add(gt)

        ct = model.ConfigTransfer(display_name=u'No Transfer')
        model.DBSession.add(ct)

    def create_alarm_states(self):
        for row in database_data.alarm_states:
            a = model.AlarmState()
            (a.display_name, a.alarm_level, a.sound_in, a.sound_out, a.internal_state) = row
            model.DBSession.add(a)

    def create_attribute_types(self):
        for row in database_data.attribute_types:
            at = model.AttributeType()
            try:
                (at.display_name, at.ad_command,
                    at.ad_parameters, at_ad_validate, at.ad_enabled, 
                    default_poller_set, default_sla, default_graph,
                    at.rra_cf, at.rra_rows,
                    at.break_by_card, at.permit_manual_add,
                    at.required_sysobjid, fields, rrds
                    ) = row
            except ValueError:
                print "problem with row", row
                raise
            self.atype_refs[at.display_name] = (
                    default_poller_set, default_sla, default_graph)
            model.DBSession.add(at)

            field_position = 0
            for field in fields:
                f = model.AttributeTypeField()
                (f.display_name, f.tag, f.description,f.showable_edit, f.showable_discovery, f.overwritable, f.tracked, f.default_value, f.parameters, f.backend) = field
                f.position = field_position
                field_position += 1
                at.fields.append(f)
            rrd_position = 0
            for rrd in rrds:
                r = model.AttributeTypeRRD()
                (r.display_name, r.name, r.data_source_type, r.range_min, r.range_max, r.range_max_field) = rrd
                r.position = rrd_position
                rrd_position += 1
                at.rrds.append(r)
    
    def fix_attribute_types(self):
        default_sla = model.Sla.by_display_name(u'No SLA')
        default_gt = model.GraphType.by_display_name(u'No Graph')
        for at_name,at_refs in self.atype_refs.items():
            ps = model.PollerSet.by_display_name(at_refs[0])
            if ps is None:
                raise ValueError("Bad default PollerSet name \"{}\" for AttributeType {}.".format(at_refs[0], at_name))
            if at_refs[1] == '':
                sla = default_sla
            else:
                sla = model.Sla.by_display_name(at_refs[1])
            if sla is None:
                raise ValueError("Bad default SLA name \"{}\" for AttributeType {}.".format(at_refs[1], at_name))
            if at_refs[2] == '':
                gt = default_gt
            else:
                gt = model.GraphType.by_display_name(at_refs[2])
            if gt is None:
                raise ValueError("Bad default GraphType name \"{}\" for AttributeType {}.".format(at_refs[2], at_name))
            
            model.DBSession.query(model.AttributeType).filter(model.AttributeType.display_name == at_name).update({'default_poller_set_id': ps.id, 'default_sla_id': sla.id, 'default_graph_type_id': gt.id})

    def create_autodiscovery(self):
        for row in database_data.autodiscovery_policies:
            p = model.AutodiscoveryPolicy()
            (p.display_name,p.set_poller,p.permit_add,p.permit_delete,
                    p.alert_delete,p.permit_modify,p.permit_disable,
                    p.skip_loopback,p.check_state,p.check_address)=row
            model.DBSession.add(p)

    def create_backends(self):
        for row in database_data.backends:
            be = model.Backend()
            (be.display_name, be.command, be.parameters) = row
            if be.command == 'event':
                parms = be.parameters.split(',')
                event_type = model.EventType.by_tag(parms[0])
                if event_type is None:
                    raise ValueError("EventType {0} not found in backend {1}".format(parms[0], be.display_name))
                self.used_event_types.append(event_type.id)
            model.DBSession.add(be)

    def create_config_transfers(self):
        for row in database_data.config_transfers:
            ct = model.ConfigTransfer(row[0], row[1])
            model.DBSession.add(ct)

    def create_event_types(self):
        for row in database_data.event_types:
            et = model.EventType()
            try:
                (et.display_name, severity, et.tag, et.text, et.generate_alarm, ignore_up_event_id, et.alarm_duration, et.show_host) = row
            except ValueError as errmsg:
                print("Bad event_type \"{0}\".\n{1}".format(row, errmsg))
                exit()
            et.severity = model.EventSeverity.by_name(severity)
            model.DBSession.add(et)

    def create_graph_types(self):
        for row in database_data.graph_types:
            gt = model.GraphType()
            try:
                (gt.display_name, atype_name, gt.title, gt.vertical_label, gt.extra_options, graph_defs, graph_vnames, graph_lines ) = row
            except ValueError as errmsg:
                raise ValueError('{}\nRow:{}'.format(errmsg, row))
            attribute_type = model.AttributeType.by_display_name(atype_name)
            if attribute_type is None:
                raise ValueError("Attribute Type {} not found in GraphType {}".format(atype_name, gt.display_name))
            gt.attribute_type_id = attribute_type.id
            for graph_def in graph_defs:
                at_rrd = model.AttributeTypeRRD.by_name(attribute_type, graph_def[1])
                if at_rrd is None:
                    raise ValueError("AttributeTypeRRD {} not found in GraphType {}".format(graph_def[1], gt.display_name))
                gt_def = model.GraphTypeDef(gt, graph_def[0], at_rrd)
                gt.defs.append(gt_def)

            position=0
            for vname in graph_vnames:
                vn = model.GraphTypeVname()
                (def_type, vn.name, vn.expression) = vname
                vn.set_def_type(def_type)
                vn.position = position
                gt.vnames.append(vn)

            position = 0
            for graph_line in graph_lines:
                gl = model.GraphTypeLine()
                gl.position = position

                if graph_line[0] == 'COMMENT':
                    gl.set_comment(*graph_line[1:])
                elif graph_line[0] == 'HRULE':
                    gl.set_hrule(*graph_line[1:])
                else:
                    vname = gt.vname_by_name(graph_line[1])
                    if vname is None:
                        raise ValueError('Vname {} not found in GraphType {}'.format(graph_line[1], gt.display_name))
                    try:
                        if graph_line[0] == 'PRINT':
                            gl.set_print(vname, graph_line[2])
                        elif graph_line[0] == 'GPRINT':
                            gl.set_gprint(vname, graph_line[2])
                        elif graph_line[0] == 'VRULE':
                            gl.set_vrule(vname, *graph_line[2:])
                        elif graph_line[0] == 'LINE':
                            gl.set_line(vname, *graph_line[2:])
                        elif graph_line[0] == 'AREA':
                            gl.set_area(vname, *graph_line[2:])
                        elif graph_line[0] == 'TICK':
                            gl.set_tick(vname, *graph_line[3:])
                        else:
                            raise ValueError('Bad GraphTypeLine type {} in GraphType {}'.format(graph_line[0], gt.display_name))
                    except GraphTypeLineError as err:
                        raise GraphTypeLineError(
                            'Error in GraphTypeLine {} in GraphType {} - {}'.format(
                                graph_line, gt.display_name, err))

                position += 1
                gt.lines.append(gl)

            model.DBSession.add(gt)

    def create_pollers(self):
        for row in database_data.pollers:
            p = model.Poller()
            (p.field, dn, p.command, p.parameters) = row
            p.display_name = unicode(dn)
            model.DBSession.add(p)

    def create_poller_sets(self):
        no_backend = model.Backend.by_display_name(u'No Backend')
        for row in database_data.poller_sets:
            (ps_name, at_name, poller_rows) = row
            atype = model.AttributeType.by_display_name(at_name)
            if atype is None:
                raise ValueError("Attribute type {0} not found.".format(at_name))
            ps = model.PollerSet(ps_name)
            ps.attribute_type = atype
            poller_row_pos = 0
            for poller_row in poller_rows:
                pr = model.PollerRow()
                pr.poller = model.Poller.by_display_name(poller_row[0])
                if pr.poller is None:
                    raise ValueError("Bad poller name \"{0}\".".format(poller_row[0]))
                if poller_row[1] == u'':
                    pr.backend = no_backend
                else:
                    pr.backend = model.Backend.by_display_name(poller_row[1])
                    if pr.backend is None:
                        raise ValueError("Bad backend name \"{0}\".".format(poller_row[1]))
                pr.position = poller_row_pos
                poller_row_pos += 1
                ps.poller_rows.append(pr)
            model.DBSession.add(ps)

    def create_severities(self):
        for severity in database_data.event_severities:
            sv = model.EventSeverity(severity[0],severity[1],severity[2],severity[3])
            model.DBSession.add(sv)

    def create_logmatches(self):
        logmatch_set = model.LogmatchSet(display_name=u'Default')
        model.DBSession.add(logmatch_set)

        for row in database_data.logfiles:
            lf = model.Logfile(row[0],row[1])
            lf.logmatchset = logmatch_set
            model.DBSession.add(lf)

        for row in database_data.logmatch_default_rows:
            lmr = model.LogmatchRow()
            try:
                (lmr.match_text, lmr.match_start, lmr.host_match, 
                    lmr.attribute_match, lmr.state_match, event_tag,
                    fields) = row
            except Exception as errmsg:
                raise ValueError("Cannot add row \"%s\": %s.\n" % (row[0], errmsg))
            else:
                lmr.event_type = model.EventType.by_tag(event_tag)
                if lmr.event_type is None:
                    raise ValueError("Bad EventType tag \"{}\" in LogMatchRow {}".format(event_tag, lmr.match_text))
                self.used_event_types.append(lmr.event_type.id)
                try:
                  lmr.match_sre = re.compile(row[0])
                except re.error as errmsg:
                    raise re.error("Cannot compile message \"%s\": %s" % (row[0],errmsg))
                lmr.logmatch_set = logmatch_set
                if fields is not None:
                    for field in fields:
                        lmf = model.LogmatchField()
                        try:
                            (lmf.event_field_tag, lmf.field_match)=field
                        except ValueError:
                            raise ValueError(
                                "Bad Field \"{}\" in LogMatchRow {}".format(
                                    field, lmr.match_text))
                        lmr.fields.append(lmf)
                model.DBSession.add(lmr)

    def create_slas(self):
        for row in database_data.slas:
            s = model.Sla()
            (s.display_name, s.event_text, attribute_type, sla_rows) = row
            s.attribute_type = model.AttributeType.by_display_name(attribute_type)
            if s.attribute_type is None:
                raise ValueError("Bad AttributeType name \"{}\" in SLA {}".format(attribute_type, s.display_name))
            model.DBSession.add(s)
            position=1
            for sla_row in sla_rows:
                sr = model.SlaRow(s,position=position)
                (sr.expression, sr.oper, sr.limit, sr.show_result, sr.show_info, sr.show_expression, sr.show_unit) = sla_row
                position += 1
                model.DBSession.add(sr)

    def create_snmp_communities(self):
        for row in database_data.snmp_communities:
            c = model.SnmpCommunity()
            (c.display_name, c.readonly, c.readwrite, c.trap) = row
            model.DBSession.add(c)

    def create_triggers(self):
        for trigger in database_data.triggers:
            t = model.Trigger(trigger[0], trigger[1])
            t.email_owner =trigger[2]
            t.email_users =trigger[3]
            t.subject = trigger[4]
            t.body = trigger[5]
            for rule in trigger[6]:
                r = model.TriggerRule()
                (field, r.oper, limits, r.stop, r.and_rule) = rule
                r.set_field(field)
                r.set_limit(limits)
                t.append(r)
            model.DBSession.add(t)
