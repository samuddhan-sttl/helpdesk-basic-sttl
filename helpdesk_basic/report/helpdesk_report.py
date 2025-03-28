# -*- coding: utf-8 -*-
# Part of odoo. See LICENSE file for full copyright and licensing details.

from odoo import fields, models, tools


class HelpdeskReport(models.Model):
    _name = "helpdesk.report"
    _description = "Helpdesk Report"
    _auto = False

    ticket_seq = fields.Char('Sequence', default='New')
    name = fields.Char('Name', readonly=True)
    partner_id = fields.Many2one('res.partner', string='Related Partner',
                                 readonly=True)
    user_id = fields.Many2one('res.users', string='Created By',
                              readonly=True)
    issue_type_id = fields.Many2one('issue.type', string='Issue Type',
                                    readonly=True)
    team_id = fields.Many2one('helpdesk.team', 'Team', readonly=True)
    start_date = fields.Datetime(string='Start Date', readonly=True)
    end_date = fields.Datetime(string='End Date', readonly=True)
    stage_id = fields.Many2one('helpdesk.stage', string='Stage')
    description = fields.Text(string='Description', readonly=True)
    priority = fields.Selection([('low', 'Low'), ('medium', 'Medium'),
                                 ('high', 'High')])

    def init(self):
        tools.drop_view_if_exists(self._cr, 'helpdesk_report')
        self._cr.execute("""
                CREATE VIEW helpdesk_report as (
                SELECT
                    t.id as id,
                    h.ticket_seq as ticket_seq,
                    t.name as name,
                    h.partner_id as partner_id,
                    h.user_id as user_id,
                    h.issue_type_id as issue_type_id,
                    h.team_id as team_id,
                    h.start_date as start_date,
                    h.end_date as end_date,
                    h.stage_id as stage_id,
                    h.help_description as description,
                    h.priority as priority
                FROM helpdesk_team t
                INNER JOIN helpdesk_ticket h
                ON (h.team_id = t.id and h.active = True))
            """)
