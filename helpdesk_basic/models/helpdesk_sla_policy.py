# -*- coding: utf-8 -*-
from odoo import fields, models


class HelpdeskSLA(models.Model):
    _name = "helpdesk.sla"
    _order = "sequence, name"
    _description = "Helpdesk SLA Policies"

    name = fields.Char('SLA Policy Name', required=True, index=True)
    sequence = fields.Integer('Sequence', default=1, index=True)
    note = fields.Text('SLA Policy Description')
    active = fields.Boolean('Active', default=True)
    condition_team_id = fields.Many2one('helpdesk.team', string='Team', required=True)
    condition_type_id = fields.Many2one('issue.type', string='Type')
    condition_stage_id = fields.Many2one('helpdesk.stage', string='Stage', required=True)
    condition_priority = fields.Selection([
        ('0', 'All'),
        ('1', 'All but low priorities'),
        ('2', 'High & Urgent'),
        ('3', 'Urgent Only'),
    ], string='Priority', required=True, default='0')

    time_days = fields.Integer('Time to Assign')
    time_hours = fields.Integer('Time since Creation')
    time_minutes = fields.Integer('Time to First Answer')
