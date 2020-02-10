<%inherit file='nextgisweb:templates/base.mako' />
<%! 
    import json
    from datetime import datetime
    from markupsafe import Markup
    from nextgisweb.auth.api import user_cget
    from nextgisweb.audit.util import _

    NBSP = Markup("&nbsp;")
%>

<%def name="head()">
    <script>
        require([
            "dojo/ready",
            "dojo/parser",
            "ngw-audit/JournalFilter/JournalFilter",
            "ngw-pyramid/NGWButton/NGWButton"
        ], function(
            ready,
            parser
        ){
            ready(function() {
                parser.parse();
            });
        });
    </script>
    <style>
        .journal-table{
            table-layout: fixed;
        }

        .journal-table .circle{
            position: relative;
            top: -1;
            margin-right: 1px;
        }

        .journal-table tr:hover td:first-child{
            color: #076dbf;
        }
    </style>    
</%def>

<%
    users = [dict(label=_('All users'), value='*')]
    users.extend(
        map(
            lambda u: dict(
                label=u.get('display_name'), value=u.get('keyname'),
                selected=(True if u.get('keyname') == user else False)),
            filter(lambda u: not u.get('system'), user_cget(request)),
        )
    )
%>

<div class="journal-toolbar ngw-toolbar ngw-toolbar--space-between">
    <div class="ngw-toolbar__inner"
        data-dojo-type='ngw-audit/JournalFilter/JournalFilter'
        data-dojo-props='users: ${json.dumps(users) | n}, dateFrom: ${json.dumps(date_from) | n}, dateTo: ${json.dumps(date_to) | n}, defaultRange: 1, action: "${request.route_url('audit.control_panel.journal.browse')}"'>
    </div>
    <div data-dojo-type="ngw-pyramid/NGWButton/NGWButton"
        data-dojo-props="size: 'small', type: 'outlined', color: 'secondary', icon: 'publish', label: '${tr(_('Export'))}'">
    </div>   
</div>
<div class="content-box">
    <div class="table-wrapper">
        <table id="journal-table" class="journal-table pure-table pure-table-horizontal pure-table-horizontal--s">
            <colgroup>
                <col width="15%" />
                <col width="8%"/>
                <col width="10%"/>
                <col width="18%"/>
                <col width="18%" />
                <col/>
                <col/>
                <col width="15%"/>
            </colgroup>
            <thead><tr> 
                <th style="text-align: inherit;">${tr(_('Timestamp'))}</th>
                <th class="text-center">${tr(_("Status"))}</th>
                <th class="text-center">${tr(_("Method"))}</th>
                <th>${tr(_("Path"))}</th>
                <th>${tr(_("Route name"))}</th>
                <th colspan="2">${tr(_("Context"))}</th>                
                <th>${tr(_("User"))}</th>
            </tr></thead>

            <tbody class="small-text">
            
            %for hit in hits:
            <%
                rid = hit.meta.id
                ts = datetime.strptime(hit['@timestamp'], '%Y-%m-%dT%H:%M:%S.%f')
            %>
            <tr style="cursor: pointer;" onClick="window.open('${request.route_url('audit.control_panel.journal.show', id=rid)}','_blank');">
                <td title="${ts.isoformat()}">${ts.strftime('%d.%m.%Y %H:%M:%S')}</td>
                <td class="text-center">
                %if hit['response']['status_code'] >= 400:
                    <span class="circle circle--danger"></span>
                %elif hit['response']['status_code'] < 200 or hit['response']['status_code'] >= 300:
                    <span class="circle circle--secondary"></span>
                %else:
                    <span class="circle circle--success"></span>
                %endif
                    <span class="v-middle">${hit['response']['status_code']}</span>
                </td>
                <td class="text-center code-text">${hit['request']['method']}</td>
                <td class="code-text" title="${hit['request']['path']}">${hit['request']['path']}</td>
                <td class="code-text" title="${hit['response']['route_name'] if 'route_name' in hit['response'] else NBSP}">
                    ${hit['response']['route_name'] if 'route_name' in hit['response'] else NBSP}</td>
                %if 'context' in hit:
                    <td class="code-text" title="${hit['context']['model']}">${hit['context']['model']}</td>
                    <td class="code-text">${hit['context']['id']}</td>
                %else:
                    <td class="code-text" style="white-space: nowrap; opacity: .8"> --- </td>
                    <td class="code-text" style="white-space: nowrap; opacity: .8"> --- </td>
                %endif
                <td>${hit['user']['keyname'] if 'user' in hit else NBSP}</td>
            </tr>
            %endfor

            </tbody>
        </table>
    </div>
</div>