import logging
from apscheduler.schedulers.background import BackgroundScheduler
from django_apscheduler.jobstores import DjangoJobStore
from django.utils import timezone
from datetime import timedelta
from issue.models import Issue, Alert
from django.core.mail import send_mail
from users.models import CustomUser


def escalate_unattended_issues():
    # undattended = older then 48 hours or still in new status
    threshold_date = timezone.now() - timedelta(hours=48)

    unattended_issues = Issue.objects.filter(
        date_created__lt=threshold_date,
        # if its still new, agent hasnt started it
        status=Issue.Status.NEW,
        # if its pending , validator hasnt reviewd it
        validation_status=Issue.ValidationStatus.PENDING
    )

    for issue in unattended_issues:
        # check if we created an escalation alert for this issue
        alert_exists = Alert.objects.filter(
            issue=issue,
            name="ESCALATION: Unattended Issue"
        ).exists()

        if not alert_exists:
            Alert.objects.create(
                issue=issue,
                name="ESCALATION: Unattended Issue",
                status=Alert.Status.NEW
            )

            admins = CustomUser.objects.filter(role__in=[CustomUser.Role.ADMIN, CustomUser.Role.SUPERADMIN])
            admin_emails = list(admins.values_list('email', flat=True))

            #put this try catch for the email failure doesnt break the job, the failure doesnt stop the rest of the process
            logger = logging.getLogger(__name__)
            if admin_emails:
                try:
                    send_mail(
                        subject=f"ESCALATION: Unattended Issue Alert",
                        message=f"Issue '{issue.title}' (ID: {issue.id}) has been unattended for over 48 hours. Please review it immediately.",
                        from_email="noreply@townguardian.com",
                        recipient_list=admin_emails,
                    )
                except Exception as e:
                    logger.error(f"Failed to send escalation email for issue {issue.id}: {e}")


import os

def start():
    # Django autoreloader launches a watcher process and a child process
    # only the child sets RUN_MAIN=true, so this avoids starting the scheduler twice
    if os.environ.get("RUN_MAIN") != "true":
        return

    scheduler = BackgroundScheduler(timezone="UTC")
    scheduler.add_jobstore(DjangoJobStore(), "default")

    scheduler.add_job(
        escalate_unattended_issues,
        trigger="interval",
        hours=1,
        id="escalate_issues_job",
        max_instances=1,
        replace_existing=True,
    )

    scheduler.start()
    print("APScheduler started!")
