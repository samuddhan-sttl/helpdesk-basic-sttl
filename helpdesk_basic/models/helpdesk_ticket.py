# Part of odoo. See LICENSE file for full copyright and licensing details.

from odoo import api, fields, models, _, tools, SUPERUSER_ID
from odoo.exceptions import AccessError, UserError
from datetime import datetime
import uuid


class HelpdeskTicket(models.Model):
    _name = 'helpdesk.ticket'
    _inherit = ['mail.thread.cc',
                'mail.thread',
                'mail.activity.mixin',
                'utm.mixin',
                'portal.mixin',
                'rating.mixin']

    _description = 'Helpdesk Ticket'
    _rec_name = 'issue_name'

    @api.model
    def _default_stage_id(self):
        stages = self.env['helpdesk.stage'].search([], limit=1)
        return stages and stages.id or False

    @api.model
    def _read_group_stage_ids(self, stages, domain, order):
        search_domain = [('id', 'in', stages.ids)]
        if 'default_team_id' in self.env.context:
            search_domain = [
                '|', ('team_ids', '=', self.env.context['default_team_id'])] + search_domain

        stage_ids = stages._search(
            search_domain, order=order, access_rights_uid=SUPERUSER_ID)
        return stages.browse(stage_ids)

    def _default_team_id(self):
        team_id = self.env['helpdesk.team'].search(
            [('visibility_member_ids', 'in', self.env.uid)], limit=1).id
        if not team_id:
            team_id = self.env['helpdesk.team'].search([], limit=1).id
        return team_id

    def _partner_domain_from_team(self):
        team_id = self.env['helpdesk.team'].search(
            [('visibility_member_ids', 'in', self.env.uid)], limit=1)
        if not team_id:
            team_id = self.env['helpdesk.team'].search([], limit=1)
        return [('id', 'in', team_id.customer_ids.ids)]

    @api.model
    def _default_access_token(self):
        return uuid.uuid4().hex


    project_id = fields.Many2one(
        "project.project", string="Project", tracking=True)
    uid = fields.Many2one('res.users', default=lambda self: self.env.uid)
    issue_name = fields.Char(
        string='Subject', required=True, index=True, tracking=True)
    team_id = fields.Many2one(
        'helpdesk.team', string='Helpdesk Team', default=_default_team_id, tracking=True)
    help_description = fields.Text()
    active = fields.Boolean(default=True)
    tag_ids = fields.Many2many('helpdesk.tag', string='Tags')
    company_id = fields.Many2one(
        related='team_id.company_id', string='Company', store=True, readonly=True)
    user_id = fields.Many2one(
        'res.users', string='Assigned to', tracking=True)
    color = fields.Integer(string='Color Index')
    ticket_seq = fields.Char('Ticket No', default='New', copy=False)
    priority = fields.Selection([('1', 'Low'), ('2', 'Medium'),
                                 ('3', 'High'), ('4', 'Urgent')], default='1')
    partner_id = fields.Many2one(
        'res.partner', string='Related Partner', domain=_partner_domain_from_team, tracking=True)
    partner_name = fields.Char('Customer Name')
    email = fields.Char(string='Email', required=True)
    issue_type_id = fields.Many2one(
        'issue.type', string='Issue Type', store=True)
    start_date = fields.Datetime(
        string='Ticket Created Date', default=fields.Datetime.now, tracking=True)
    end_date = fields.Datetime(string='Ticket Close Date', tracking=True)
    attachment_ids = fields.One2many('ir.attachment', compute='_compute_attachments',
                                     string="Main Attachments", help="Attachment that don't come from message.")
    attachments_count = fields.Integer(compute='_compute_attachments',
                                       string='Add Attachments')
    is_accessible = fields.Boolean('Is Accessible',
                                   compute='_compute_is_accessible')
    is_assigned = fields.Boolean('Is Asigned',
                                 compute='_compute_is_accessible')
    stage_id = fields.Many2one('helpdesk.stage', string='Stage', index=True, tracking=True, readonly=False,
                               store=True, copy=False, ondelete='restrict', default=_default_stage_id, group_expand='_read_group_stage_ids')
    stage_type = fields.Selection(
        related="stage_id.stage_type", string='Stage Type', readonly=True)
    feedback = fields.Text('Comment', help="Reason of the rating")

    rating_last_value = fields.Float('Rating Last Value', groups='base.group_user',
                                     compute='_compute_rating_last_value', compute_sudo=True, store=True)
    is_rating = fields.Boolean("Is Rating")
    sla_name = fields.Char(string='Failed SLA Policy',
                           compute='_get_sla_id', store=True)
    sla_id = fields.Many2one(
        'helpdesk.sla', string='Failed SLA Policy ID', compute='_get_sla_id', store=True)
    last_date = fields.Datetime(
        string='Deadline', compute='_get_sla_id', store=True)
    # active = fields.Boolean('Active', default=True)
    sla_fail = fields.Boolean(
        string='Failed SLA Policy', compute='_get_sla_fail', store=True)
    # company_id = fields.Many2one(
    #     'res.company', related="team_id.company_id", string='Company')
    contact_type = fields.Selection(
        [('email', 'Email'), ('phone', 'Phone'), ('other', 'Other')])
    business_impact = fields.Boolean("Business Impact")
    close_description = fields.Text(tracking=True)
    expected_delivery_date = fields.Date(string='Expected Delivery Date')
    access_token = fields.Char('Access Token', default=_default_access_token)


    @api.model_create_multi
    def create(self, values):
        tickets = super(HelpdeskTicket, self).create(values)
        for ticket in tickets:
            if not ticket.ticket_seq or ticket.ticket_seq == _('New'):
                ticket.ticket_seq = self.env['ir.sequence'].next_by_code('helpdesk.ticket') or _('New')

            ticket.partner_name = ticket.partner_id.name

            if ticket.issue_type_id and not ticket.team_id:
                ticket.team_id = self.env['helpdesk.team'].search([('issue_type_ids', '=', ticket.issue_type_id.id)],
                                                                  limit=1).id
                if not self.stage_id:
                    self.stage_id = self.team_id.stage_ids[0]

            # ---------------mail to related partner ----
            ticket.team_id.mail_template_id.send_mail(ticket.id, force_send=True)

            # ---------------mail to team member----
            if ticket.team_id.notify_team_on_ticket_creation:
                cleaned_ctx = dict(self.env.context)
                cleaned_ctx.update({
                    'email_to_members': ", ".join(ticket.team_id.member_ids.mapped('partner_id').mapped('email')),
                })
                team_member_template_id = self.env.ref(
                    'helpdesk_basic.new_ticket_team_member_mail_template')
                team_member_template_id.with_context(cleaned_ctx).send_mail(ticket.id, force_send=True)

            ticket.message_subscribe(partner_ids=ticket.partner_id.ids)
        return tickets

    def write(self, vals):
        result = super(HelpdeskTicket, self).write(vals)
        # if vals.get('user_id') and self.team_id.notify_assignee_on_ticket_creation:
        #     assignee_template_id = self.env.ref(
        #         'helpdesk_basic.ticket_assignee_mail_template')
        #     assignee_template_id.send_mail(self.id, force_send=True)

        # ------------------send mail to customer on ticket assigned
        if vals.get('user_id') and self.team_id.notify_customer_on_ticket_assigned:
            ticket_assign_customer_template_id = self.env.ref(
                'helpdesk_basic.customer_ticket_assignee_mail_template')
            ticket_assign_customer_template_id.send_mail(self.id, force_send=True)

        # ------------------send mail to customer on ticket cancel or close
        if vals.get('stage_id') and self.stage_id.mail_stage_tmpl_id and self.team_id.notify_on_stage_change:
            self.stage_id.mail_stage_tmpl_id.send_mail(self.id, force_send=True)

        return result

    @api.model
    def default_get(self, default_fields):
        vals = super(HelpdeskTicket, self).default_get(default_fields)
        if 'team_id' not in default_fields:
            team_id = self._default_team_id()
            vals.update({'team_id': team_id})

        if 'team_id' in vals:
            user_dict = {}
            team_id = self.env['helpdesk.team'].search(
                [("id", "=", vals['team_id'])])

            if team_id.assignment_method == 'balanced':
                for rec in team_id.member_ids.ids:
                    ticket = self.env['helpdesk.ticket'].search_count(
                        [('team_id', '=', team_id.id), ('user_id', '=', rec)])
                    user_dict.update({rec: ticket})
                temp = min(user_dict.values())
                res = [key for key in user_dict if user_dict[key] == temp]
                vals['user_id'] = res[0]

            if team_id.assignment_method == 'random':
                for member in team_id.member_ids:
                    vals['user_id'] = member.id
        return vals

    @api.depends('last_date', 'stage_id')
    def _get_sla_fail(self):
        for record in self:
            if record.last_date and fields.Datetime.now() > record.last_date:
                record.sla_fail = True

    @api.depends('team_id', 'stage_id', 'priority', 'issue_type_id', 'create_date')
    def _get_sla_id(self):
        for record in self:
            dom = [('condition_team_id', '=', record.team_id.id),
                   ('condition_priority', '<=', record.priority)]
            if record.issue_type_id:
                dom += ['|', ('condition_type_id', '=', False),
                        ('condition_type_id', '=', record.issue_type_id.id)]
            if record.stage_id:
                dom.append(('condition_stage_id.sequence',
                           '>=', record.stage_id.sequence))
            sla = self.env['helpdesk.sla'].search(
                dom, order="time_days, time_hours", limit=1)
            if sla and record.sla_id != sla and record.create_date and record.active:
                record.sla_id = sla
                record.sla_name = sla.name
                create_date = fields.Datetime.from_string(record.create_date)
                if sla.time_days <= 0:
                    record.last_date = fields.Datetime.to_string(create_date.replace(
                        day=create_date.day + 1, hour=create_date.hour, minute=create_date.minute))
                else:
                    record.last_date = fields.Datetime.to_string(create_date.replace(
                        day=sla.time_days, hour=sla.time_hours, minute=sla.time_minutes))

    def _compute_is_accessible(self):
        has_group = self.env.user.has_group('base.group_no_one')
        for ticket in self:
            ticket.is_accessible = ticket.is_assigned = False
            if self.env.user.partner_id.id == ticket.partner_id.id or has_group:
                ticket.is_accessible = True
            if self.env.user.id == ticket.user_id.id or has_group:
                ticket.is_assigned = True

    def _compute_attachments(self):
        for ticket in self:
            attachment_ids = self.env['ir.attachment'].search(
                [('res_model', '=', ticket._name),
                 ('res_id', '=', ticket.id)])
            ticket.attachments_count = len(attachment_ids.ids)
            ticket.attachment_ids = attachment_ids

    @api.onchange('stage_id')
    def onchange_stage_id(self):
        if self.stage_id.stage_type == 'done':
            self.end_date = datetime.today()

    @api.onchange('partner_id')
    def onchange_partner_id(self):
        if self.partner_id:
            self.email = self.partner_id.email
            return {'domain': {'project_id': [('id', 'in', self.partner_id.project_ids.ids)]}}

    @api.onchange('team_id')
    def onchange_team_id(self):
        self.user_id = False
        if self.team_id:
            self.stage_id = self.team_id.stage_ids and self.team_id.stage_ids.ids[0]
            self.partner_id = False
            return {'domain': {'partner_id': [('id', 'in', self.team_id.customer_ids.ids)]}}

    def action_assign_to_me(self):
        if not self.user_id:
            self.user_id = self.env.user

    def _merge_ticket_attachments(self, tickets):
        self.ensure_one()

        def _get_attachments(ticket_id):
            return self.env['ir.attachment'].search([('res_model', '=', self._name), ('res_id', '=', ticket_id)])

        first_attachments = _get_attachments(self.id)
        count = 1
        for ticket in tickets:
            attachments = _get_attachments(ticket.id)
            for attachment in attachments:
                values = {'res_id': self.id}
                for attachment_in_first in first_attachments:
                    if attachment.name == attachment_in_first.name:
                        values['name'] = "%s (%s)" % (attachment.name, count)
                count += 1
                attachment.write(values)
        return True

    @api.model
    def message_new(self, msg_dict, custom_values=None):
        if self.env.user.has_group('base.group_portal'):
            self = self.with_context(default_user_id=False)
        if self._uid == self.env.ref('base.user_root').id:
            self = self.with_context(default_user_id=False)

        if custom_values is None:
            custom_values = {}
        defaults = {
            'issue_name':  msg_dict.get('subject') or _("No Subject"),
            'email': msg_dict.get('from'),
            'partner_id': msg_dict.get('author_id', False),
            'team_id': custom_values.get('team_id', False),
        }

        if 'company_id' not in defaults and 'team_id' in defaults:
            defaults['company_id'] = self.env['helpdesk.team'].browse(
                defaults['team_id']).company_id.id
        return super(HelpdeskTicket, self).message_new(msg_dict, custom_values=defaults)


    def _track_subtype(self, init_values):
        self.ensure_one()
        if 'user_id' in init_values and self.user_id:
            return self.env.ref('helpdesk_basic.mt_ticket_new')
        elif 'stage_id' in init_values and self.stage_id and \
                self.stage_id.sequence <= 1:
            return self.env.ref('helpdesk_basic.mt_ticket_new')
        elif 'stage_id' in init_values:
            return self.env.ref('helpdesk_basic.mt_ticket_stage')
        return super(HelpdeskTicket, self)._track_subtype(init_values)

    def _message_get_suggested_recipients(self):
        recipients = super(
            HelpdeskTicket, self)._message_get_suggested_recipients()
        try:
            for ticket in self:
                if ticket.team_id.message_follower_ids:
                    ticket.sudo()._message_add_suggested_recipient(
                        recipients, partner=ticket.partner_id, email=ticket.email, reason=_('Customer'))
                elif ticket.email:
                    ticket.sudo()._message_add_suggested_recipient(
                        recipients, email=ticket.email, reason=_('Customer Email'))
        except AccessError:
            pass
        return recipients

    def get_valid_email(self, msg):
        emails_list = []
        valid_email = tools.email_split(
            (msg.get('to') or '') + ',' + (msg.get('cc') or ''))
        team_aliases = self.mapped('team_id.alias_name')
        for eml in valid_email:
            if eml.split('@')[0] not in team_aliases:
                emails_list += [eml]
        return emails_list



    # def _track_template(self, changes):
    #     res = super(HelpdeskTicket, self)._track_template(changes)
        ticket = self[0]
        # if 'user_id' in changes and ticket.team_id.notify_customer_on_ticket_assigned:
        #     ticket_assign_customer_template_id = self.env.ref(
        #         'helpdesk_basic.customer_ticket_assignee_mail_template')
        #
        #     res['user_id'] = (ticket_assign_customer_template_id, {
        #         'auto_delete_message': True,
        #         'subtype_id': self.env['ir.model.data']._xmlid_to_res_id('mail.mt_note'),
        #         # 'email_layout_xmlid': 'mail.mail_notification_light'
        #     })

        # if 'stage_id' in changes and ticket.stage_id.mail_stage_tmpl_id and ticket.team_id.notify_on_stage_change:
        #     res['stage_id'] = (ticket.stage_id.mail_stage_tmpl_id, {
        #         'auto_delete_message': True,
        #         'subtype_id': self.env['ir.model.data']._xmlid_to_res_id('mail.mt_note'),
        #         # 'email_layout_xmlid': 'mail.mail_notification_light'
        #     })




        # if ticket.stage_id.stage_type == 'draft':
        #     if 'stage_id' in changes and ticket.team_id.mail_template_id:
        #         res['team_id'] = (ticket.team_id.mail_template_id, {
        #             'auto_delete_message': True,
        #             'subtype_id': self.env['ir.model.data']._xmlid_to_res_id('mail.mt_note'),
        #             'email_layout_xmlid': 'mail.mail_notification_light'
        #         })
        # if ticket.stage_id.stage_type == 'done':
        #     if 'stage_id' in changes and ticket.team_id.mail_close_tmpl_id:
        #         res['team_id'] = (ticket.team_id.mail_close_tmpl_id, {
        #             'auto_delete_message': True,
        #             'subtype_id': self.env['ir.model.data']._xmlid_to_res_id('mail.mt_note'),
        #             'email_layout_xmlid': 'mail.mail_notification_light'
        #         })
        # return res

    def _auto_rating_request_mail(self):
        ticket_ids = self.env['helpdesk.ticket'].search([])
        for ticket in ticket_ids.filtered(
                lambda r: r.stage_id.stage_type == 'done' and r.team_id.is_rating == True):
            template = self.env.ref(
                'helpdesk_basic.ticket_rating_mail_template')
            if ticket.is_rating != True:
                template.send_mail(res_id=ticket.id, force_send=True)
                ticket.is_rating = True
