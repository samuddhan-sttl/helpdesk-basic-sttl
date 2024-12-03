from odoo import models
import datetime
import time
import pytz

class ResolvedTicketsXls(models.AbstractModel):
    _name = "report.helpdesk_basic.resolved_tickets_xls"
    _inherit = "report.report_xlsx.abstract"

    def get_tz_date(self, date=None, timezone=None):
        to_zone = pytz.timezone(timezone)
        from_zone = pytz.timezone('UTC')
        return from_zone.localize(date).astimezone(to_zone)

    def generate_xlsx_report(self, workbook, data, doc):

        worksheet = workbook.add_worksheet()

        centered = workbook.add_format({'align': 'center'})
        table_header_format = workbook.add_format({'align': 'center', 'border': 1, 'bold': True})

        table_headers = ['Ticket No', 'Subject', 'Customer', 'Project Name', 'Assigned To', 'Helpdesk Team', 'Stage', 'Created Date', 'Resolved Date','Created Time', 'Resolved Time', 'Resolved Time Hours']
        col = 0
        for headers in table_headers:
            worksheet.write(0, col, headers, table_header_format)
            col += 1

        for col in range(8):
            worksheet.set_column(col, col, 5 * 4)  # Converting cm to the unit of characters

        timezone = self._context.get('tz') or self.env.user.tz
        row = 1
        for line in doc:

            start_date_time = self.get_tz_date(line.start_date, self.env.user.tz).strftime('%H:%M')
            resolved_date_time = self.get_tz_date(line.resolved_date, self.env.user.tz).strftime('%H:%M') if line.resolved_date else ''
            total_time = None
            if line.resolved_date and line.start_date:
                time_difference = self.get_tz_date(line.resolved_date, self.env.user.tz) - self.get_tz_date(
                    line.start_date, self.env.user.tz)

                total_seconds = int(time_difference.total_seconds())

                hours = total_seconds // 3600
                minutes = (total_seconds % 3600) // 60
                seconds = total_seconds % 60

                total_time = f"{hours:02}:{minutes:02}:{seconds:02}"


            # print('^^^^^^^^^^^^^',resolved_date_time_obj)

            worksheet.write(row, 0, line.ticket_seq if line.ticket_seq else 'NA', centered)
            worksheet.write(row, 1, line.issue_name if line.issue_name else 'NA', centered)
            worksheet.write(row, 2, line.partner_id.name if line.partner_id else 'NA', centered)
            worksheet.write(row, 3, line.project_id.name if line.partner_id else 'NA', centered)
            worksheet.write(row, 4, line.user_id.name if line.user_id else 'NA', centered)
            worksheet.write(row, 5, line.team_id.name if line.team_id else 'NA', centered)
            worksheet.write(row, 6, line.stage_id.name if line.stage_id else 'NA', centered)
            worksheet.write(row, 7, line.start_date.strftime('%m/%d/%Y') if line.start_date else 'NA', centered)
            worksheet.write(row, 8, line.resolved_date.strftime('%m/%d/%Y') if line.resolved_date else 'NA', centered)
            worksheet.write(row, 9, str(start_date_time) if line.resolved_date else 'NA', centered)
            worksheet.write(row, 10,str(resolved_date_time)if line.resolved_date else 'NA', centered)
            worksheet.write(row, 11,total_time if line.resolved_date else 'NA', centered)
            row += 1