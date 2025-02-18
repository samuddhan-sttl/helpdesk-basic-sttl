# Part of odoo. See LICENSE file for full copyright and licensing details.

from odoo import api, fields, models, _, tools, SUPERUSER_ID
from odoo.exceptions import AccessError, UserError
from datetime import datetime, timedelta
import uuid



TICKET_PRIORITY = [
    ('0', 'All'),
    ('1', 'Low priority'),
    ('2', 'High priority'),
    ('3', 'Urgent'),
]


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
            search_domain = ['|', ('team_ids', '=', self.env.context['default_team_id'])] + search_domain

        stage_ids = stages._search(search_domain, order=order, access_rights_uid=SUPERUSER_ID)
        return stages.browse(stage_ids)

    def _default_team_id(self):
        team_id = self.env['helpdesk.team'].search([('visibility_member_ids', 'in', self.env.uid)], limit=1).id
        if not team_id:
            team_id = self.env['helpdesk.team'].search([], limit=1).id
        return team_id

    uid = fields.Many2one('res.users', default=lambda self: self.env.uid)
    issue_name = fields.Char(string='Subject', required=True, index=True, tracking=True)
    team_id = fields.Many2one('helpdesk.team', string='Helpdesk Team', default=_default_team_id, tracking=True)
    help_description = fields.Text()
    active = fields.Boolean(default=True)
    tag_ids = fields.Many2many('helpdesk.tag', string='Tags')
    company_id = fields.Many2one(related='team_id.company_id', string='Company', store=True, readonly=True)
    user_id = fields.Many2one(
        'res.users', string='Assigned to',tracking=True)
    color = fields.Integer(string='Color Index')
    ticket_seq = fields.Char('Ticket No', default='New', copy=False)
    priority = fields.Selection([('0', 'Very Low'), ('1', 'Low'), ('2', 'Medium'),
                                 ('3', 'High')], default='0')
    partner_id = fields.Many2one('res.partner', string='Related Partner', tracking=True)
    partner_name = fields.Char('Customer Name')
    email = fields.Char(string='Email', required=True)
    issue_type_id = fields.Many2one('issue.type', string='Issue Type', store=True)
    start_date = fields.Datetime(
            string='Ticket Created Date', default=fields.Datetime.now, tracking=True, readonly=True)
    end_date = fields.Datetime(string='Ticket Close Date', tracking=True)
    attachment_ids = fields.One2many('ir.attachment', compute='_compute_attachments', string="Main Attachments", help="Attachment that don't come from message.")
    attachments_count = fields.Integer(compute='_compute_attachments',
                                       string='Add Attachments')
    is_accessible = fields.Boolean('Is Accessible',
                                   compute='_compute_is_accessible')
    is_assigned = fields.Boolean('Is Asigned',
                                 compute='_compute_is_accessible')
    stage_id = fields.Many2one('helpdesk.stage', string='Stage', index=True, tracking=True, readonly=False, store=True, copy=False, ondelete='restrict', default=_default_stage_id, group_expand='_read_group_stage_ids')
    stage_type = fields.Selection(related="stage_id.stage_type", string='Stage Type', readonly=True)
    feedback = fields.Text('Comment', help="Reason of the rating")

    rating_last_value = fields.Float('Rating Last Value', groups='base.group_user', compute='_compute_rating_last_value', compute_sudo=True, store=True)
    is_rating = fields.Boolean("Is Rating")
    sla_name = fields.Char(string='Failed SLA Policy', compute='_get_sla_id', store=True)
    sla_id = fields.Many2one('helpdesk.sla', string='Failed SLA Policy ID', compute='_get_sla_id', store=True)
    last_date = fields.Datetime(string='Deadline', compute='_get_sla_id', store=True)
    active = fields.Boolean('Active', default=True)
    sla_fail = fields.Boolean(string='Failed SLA Policy', compute='_get_sla_fail', store=True)
    company_id = fields.Many2one('res.company', related="team_id.company_id", string='Company')
    contact_type = fields.Selection([('email', 'Email'), ('phone', 'Phone'), ('other', 'Other')])
    business_impact = fields.Boolean("Business Impact")
    close_description = fields.Text(tracking=True)

    resolved_date = fields.Datetime(string="Resolved Date", compute='_compute_resolved_date')
    contact_number = fields.Char(string='Contact Number', readonly=True)


    @api.depends('last_date', 'stage_id')
    def _get_sla_fail(self):
        for record in self:
            if record.last_date and fields.Datetime.now() > record.last_date:
                record.sla_fail = True

    @api.depends('team_id', 'stage_id', 'priority', 'issue_type_id', 'create_date')
    def _get_sla_id(self):
        for record in self:
            dom = [('condition_team_id', '=', record.team_id.id), ('condition_priority', '<=', record.priority)]
            if record.issue_type_id:
                dom += ['|', ('condition_type_id', '=', False), ('condition_type_id', '=', record.issue_type_id.id)]
            if record.stage_id:
                dom.append(('condition_stage_id.sequence', '>=', record.stage_id.sequence))
            sla = self.env['helpdesk.sla'].search(dom, order="time_days, time_hours", limit=1)
            if sla and record.sla_id != sla and record.create_date and record.active:
                record.sla_id = sla
                record.sla_name = sla.name
                create_date = fields.Datetime.from_string(record.create_date)
                if sla.time_days <= 0:
                    record.last_date = create_date + timedelta(days=1)
                else:
                    record.last_date = create_date + timedelta(days=sla.time_days, hours=sla.time_hours, minutes=sla.time_minutes)

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

    @api.depends('user_id')
    def _compute_team_id(self):
        for team in self:
            if not team.user_id:
                continue
            user = team.user_id
            if team.team_id and user in team.team_id.member_ids | team.team_id.user_id:
                continue
            team = self.env['helpdesk.team']._get_default_team_id(user_id=user.id)
            team.team_id = team.id

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
            defaults['company_id'] = self.env['helpdesk.team'].browse(defaults['team_id']).company_id.id
        return super(HelpdeskTicket, self).message_new(msg_dict, custom_values=defaults)

    @api.model
    def _default_access_token(self):
        return uuid.uuid4().hex

    access_token = fields.Char('Access Token', default=_default_access_token)

    
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

    @api.onchange('stage_id')
    def onchange_end_date(self):
        if self.stage_id.stage_type == 'done':
            self.end_date = datetime.today()
            
    def _creation_subtype(self):
        return self.env.ref('helpdesk_basic.mt_ticket_new')
    
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
        recipients = super(HelpdeskTicket, self)._message_get_suggested_recipients()
        try:
            for ticket in self:
                if ticket.team_id.message_follower_ids:
                    ticket.sudo()._message_add_suggested_recipient(recipients, partner=ticket.partner_id, reason=_('Customer'))
                elif ticket.email:
                    ticket.sudo()._message_add_suggested_recipient(recipients, email=ticket.email, reason=_('Customer Email'))
        except AccessError:
            pass
        return recipients

    def get_valid_email(self, msg):
        emails_list = []
        valid_email = tools.email_split((msg.get('to') or '') + ',' + (msg.get('cc') or ''))
        team_aliases = self.mapped('team_id.alias_name')
        for eml in valid_email:
            if eml.split('@')[0] not in team_aliases:
                emails_list+= [eml]
        return emails_list
 
    @api.model_create_multi 
    def create(self, values):
        for vals in values:
            if not vals.get('ticket_seq') or vals['ticket_seq'] == _('New'):
                vals['ticket_seq'] = self.env['ir.sequence'].next_by_code('helpdesk.ticket') or _('New')

            partner_id = vals.get('partner_id', False)
            partner_name = vals.get('email', False)
            partner_email = vals.get('email', False)
            if partner_email and partner_name and not partner_id:
                # try:
                #     # if len(self.get_valid_email({'to': partner_email, 'cc': ''})) < 1:
                #     #     raise UserError(_("Invalid Email!"))

                #     vals['partner_id'] = self.env['res.partner'].find_or_create(
                #         self.get_valid_email({'to': partner_email, 'cc':''})[0]).id
                # except UnicodeEncodeError:
                    
                vals['partner_id'] = self.env['res.partner'].create({
                    'name': partner_name,
                    'email': partner_email,
                }).id

        partners = self.env['res.partner'].browse([vals['partner_id'] for vals in values if 'partner_id' in vals and vals.get('partner_id') and 'email' not in vals])
        partner_name_map = {partner.id: partner.name for partner in partners}

        for vals in values:
            if vals.get('issue_type_id'):
                team = self.env['helpdesk.team'].search([('issue_type_ids', '=', int(vals.get('issue_type_id')))])
                if team:
                    vals.update({'team_id': team.id})
            if vals.get('partner_id') in partner_name_map:
                vals['partner_name'] = partner_name_map.get(vals['partner_id'])

            if vals.get('team_id'):
                team = self.team_id.browse(vals.get('team_id'))
                vals.update(
                    {'stage_id': team.stage_ids and team.stage_ids[0].id or False})
            if not self.stage_id and self.team_id and self.team_id.stage_ids:
                self.stage_id = self.team_id.stage_ids[0]

        tickets = super(HelpdeskTicket, self).create(values)
        for ticket in tickets:
            ticket.team_id.mail_template_id.send_mail(ticket.id)
            if ticket.partner_id:
                ticket.message_subscribe(partner_ids=ticket.partner_id.ids)

        return tickets

    def _track_template(self, changes):
        res = super(HelpdeskTicket, self)._track_template(changes)
        ticket = self[0]
        if ticket.stage_id.stage_type == 'draft':
            if 'stage_id' in changes and ticket.team_id.mail_template_id:
                res['team_id'] = (ticket.team_id.mail_template_id, {
                    'auto_delete_message': True,
                    'subtype_id': self.env['ir.model.data']._xmlid_to_res_id('mail.mt_note'),
                    'email_layout_xmlid': 'mail.mail_notification_light'
                }
            )
        if ticket.stage_id.stage_type == 'done':
            if 'stage_id' in changes and ticket.team_id.mail_close_tmpl_id:
                res['team_id'] = (ticket.team_id.mail_close_tmpl_id, {
                    'auto_delete_message': True,
                    'subtype_id': self.env['ir.model.data']._xmlid_to_res_id('mail.mt_note'),
                    'email_layout_xmlid': 'mail.mail_notification_light'
                }
            )
        return res

    @api.onchange('partner_id')
    def onchange_partner_id(self):
        if self.partner_id:
            self.email = self.partner_id.email

    @api.onchange('team_id')
    def onchange_team_id(self):
        self.user_id = False
        if self.team_id:
            self.stage_id = self.team_id.stage_ids and self.team_id.stage_ids.ids[0]

    def _compute_is_accessible(self):
        has_group = self.env.user.has_group('base.group_no_one')
        for ticket in self:
            if self.env.user.partner_id.id == ticket.partner_id.id or \
                    has_group:
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

    def _auto_rating_request_mail(self):
        ticket_ids = self.env['helpdesk.ticket'].search([])
        for ticket in ticket_ids.filtered(
                lambda r: r.stage_id.stage_type == 'done' and r.team_id.is_rating == True):
            template = self.env.ref('helpdesk_basic.ticket_rating_mail_template')
            if ticket.is_rating != True:
                template.send_mail(res_id=ticket.id, force_send=True)
            ticket.is_rating = True

    @api.depends('message_ids')
    def _compute_resolved_date(self):
        for record in self:
            resolved_date = None
            for msg in record.sudo().message_ids:
                if msg.subtype_id.name == "Stage Changed":
                    for tracking in msg.tracking_value_ids:
                        if tracking.new_value_char == "Resolved":
                            resolved_date = msg.date
                            break
                if resolved_date:
                    break
            if resolved_date:
                record.resolved_date = resolved_date
            else:
                record.resolved_date = False