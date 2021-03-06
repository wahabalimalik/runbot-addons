# -*- coding: utf-8 -*-
# Copyright <2017> <Vauxoo info@vauxoo.com>
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

import logging

from openerp import models

from .runbot_repo import _get_url, _get_session

_logger = logging.getLogger(__name__)


class RunbotBuild(models.Model):
    _inherit = "runbot.build"

    def github_status(self, cr, uid, ids, context=None):
        runbot_domain = self.pool['runbot.repo'].domain(cr, uid)
        for build in self.browse(cr, uid, ids, context=context):
            is_merge_request = build.branch_id.branch_name.isdigit()
            source_project_id = False
            _url = _get_url('/projects/:owner/:repo/statuses/%s' % build.name,
                            build.repo_id.base)
            if not build.repo_id.uses_gitlab:
                super(RunbotBuild, self).github_status(cr, uid, ids,
                                                       context=context)
                continue
            if not build.repo_id.token:
                continue
            session = _get_session(build.repo_id.token)
            try:
                if is_merge_request:
                    url = _get_url('/projects/:owner/:repo/merge_requests/'
                                   '?iid=%s' % build.branch_id.branch_name,
                                   build.repo_id.base)
                    response = session.get(url)
                    response.raise_for_status()
                    json = response.json()[0]
                    source_project_id = json['source_project_id']
                    if source_project_id:
                        url = _get_url('/projects/%s' % source_project_id,
                                       build.repo_id.base)
                        response = session.get(url)
                        response.raise_for_status()
                        json = response.json()
                        base_url = (json['web_url'].replace('http://', '').
                                    replace('https://', ''))
                        _url = _get_url('/projects/:owner/:repo/statuses/%s' %
                                        build.name, base_url)
                desc = "runbot build %s" % (build.dest,)
                if build.state == 'testing':
                    state = 'running'
                elif build.state in ('running', 'done'):
                    state = 'failed'
                    if build.result == 'ok':
                        state = 'success'
                    if build.result == 'ko':
                        state = 'failed'
                    if build.result == 'skipped':
                        state = 'canceled'
                    if build.result == 'killed':
                        state = 'canceled'
                    desc += " (runtime %ss)" % (build.job_time,)
                else:
                    continue
                status = {
                    "state": state,
                    "target_url": "http://%s/runbot/build/%s" % (runbot_domain,
                                                                 build.id),
                    "description": desc,
                    "context": "ci/runbot"
                }
                _logger.debug("gitlab updating status %s to %s", build.name,
                              state)
                response = session.post(_url, status)
                response.raise_for_status()
            except Exception:
                _logger.exception('gitlab API error %s', _url)

