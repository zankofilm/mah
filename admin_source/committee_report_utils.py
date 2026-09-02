# -*- coding: utf-8 -*-
"""تجمیع اطلاعات کمیته‌های محله برای گزارش‌ها."""


def member_display_role(member):
    roles = []
    if member.get("is_chair"):
        roles.append("رئیس کمیته")
    if member.get("is_secretary"):
        roles.append("دبیر کمیته")
    explicit = (member.get("member_role") or "").strip()
    if explicit and explicit not in roles and explicit != "عضو":
        roles.append(explicit)
    if not roles:
        roles.append(explicit or "عضو")
    return "، ".join(roles)


def get_zone_committee_report_data(db, zone_id):
    committees = db.get_zone_committees(zone_id)
    result = []
    for committee in committees:
        item = dict(committee)
        cid = item["id"]
        item["members"] = db.get_committee_members(cid)
        item["meetings"] = db.get_committee_meetings(cid)
        item["resolutions"] = db.get_committee_resolutions(cid)
        item["issues"] = db.get_committee_issues(cid)
        item["actions"] = db.get_committee_actions(cid)
        item["active_members"] = [m for m in item["members"] if (m.get("status") or "فعال") == "فعال"]
        result.append(item)
    return result


def committee_summary_rows(committees):
    rows = []
    for index, committee in enumerate(committees, start=1):
        rows.append([
            index,
            committee.get("title") or "—",
            committee.get("chair_name") or "—",
            committee.get("secretary_name") or "—",
            len(committee.get("active_members") or []),
            len(committee.get("meetings") or []),
            sum(1 for r in committee.get("resolutions") or [] if r.get("status") not in ("انجام‌شده", "لغوشده")),
            committee.get("status") or "—",
        ])
    return rows


def committee_member_rows(committees):
    rows = []
    for committee in committees:
        members = committee.get("members") or []
        if not members:
            rows.append([
                committee.get("title") or "—", "فاقد عضو ثبت‌شده", "—", "—", "—", "—", "—", "—"
            ])
            continue
        for member in members:
            rows.append([
                committee.get("title") or "—",
                member.get("person_name") or "—",
                member.get("national_code") or "—",
                member_display_role(member),
                member.get("member_type") or "—",
                member.get("agency_name") or "—",
                member.get("mobile") or "—",
                member.get("status") or "—",
            ])
    return rows


def committee_meeting_rows(committees):
    rows = []
    for committee in committees:
        for meeting in committee.get("meetings") or []:
            rows.append([
                committee.get("title") or "—",
                meeting.get("title") or "—",
                meeting.get("meeting_date") or "—",
                meeting.get("start_time") or "—",
                meeting.get("place_name") or "—",
                meeting.get("status") or "—",
            ])
    return rows


def committee_resolution_rows(committees):
    rows = []
    for committee in committees:
        for resolution in committee.get("resolutions") or []:
            rows.append([
                committee.get("title") or "—",
                resolution.get("title") or "—",
                resolution.get("responsible_person") or "—",
                resolution.get("responsible_agency") or "—",
                resolution.get("due_date") or "—",
                resolution.get("status") or "—",
                resolution.get("linked_issue_id") or "—",
                resolution.get("linked_action_id") or "—",
            ])
    return rows


def committee_link_rows(committees):
    rows = []
    for committee in committees:
        for issue in committee.get("issues") or []:
            rows.append([
                committee.get("title") or "—", "مسئله", issue.get("title") or "—",
                issue.get("related_office") or "—", issue.get("status") or "—",
            ])
        for action in committee.get("actions") or []:
            rows.append([
                committee.get("title") or "—", "اقدام", action.get("title") or "—",
                action.get("responsible_office") or "—", action.get("status") or "—",
            ])
    return rows
