"""Email service for sending job digest notifications using Resend API."""

from datetime import datetime
from typing import List, Dict, Any
from pathlib import Path

try:
    import resend
except ImportError:
    resend = None  # Will be handled in send methods

from jinja2 import Environment, FileSystemLoader, select_autoescape
import structlog
from sqlalchemy import select

from app.core.config import settings
from app.models import User

logger = structlog.get_logger()

# Initialize Resend API
if resend:
    resend.api_key = settings.resend_api_key

# Setup Jinja2 environment
TEMPLATES_DIR = Path(__file__).parent.parent / "templates"
if not TEMPLATES_DIR.exists():
    TEMPLATES_DIR.mkdir(parents=True, exist_ok=True)

jinja_env = Environment(
    loader=FileSystemLoader(str(TEMPLATES_DIR)),
    autoescape=select_autoescape(['html', 'xml'])
)


class EmailService:
    """Service for sending emails via Resend API."""

    FROM_EMAIL = "onboarding@resend.dev"
    BASE_URL = settings.frontend_url

    @staticmethod
    def _render_template(template_name: str, context: Dict[str, Any]) -> str:
        """Render a Jinja2 template with the given context."""
        try:
            template = jinja_env.get_template(template_name)
            return template.render(**context)
        except Exception as e:
            logger.error("template_render_failed", template=template_name, error=str(e))
            raise

    @staticmethod
    def send_digest(user: User, jobs: List[Dict[str, Any]]) -> bool:
        """
        Send personalized daily job digest to user.

        Args:
            user: User object with email and preferences
            jobs: List of matched jobs with details
                  Each job should have: title, company, location, url, score,
                  salary_min, salary_max, remote

        Returns:
            bool: True if email sent successfully, False otherwise
        """
        if not resend:
            logger.error("resend_not_installed", user_id=str(user.id))
            return False

        try:
            # Prepare template context
            context = {
                "user_email": user.email,
                "date": datetime.now().strftime("%B %d, %Y"),
                "year": datetime.now().year,
                "job_count": len(jobs),
                "jobs": jobs,
                "preferences_url": f"{EmailService.BASE_URL}/preferences",
                "unsubscribe_url": f"{EmailService.BASE_URL}/preferences?unsubscribe=true",
            }

            # Render HTML and text templates
            html_content = EmailService._render_template("digest.html", context)
            text_content = EmailService._render_template("digest.txt", context)

            # Send email via Resend
            params = {
                "from": EmailService.FROM_EMAIL,
                "to": [user.email],
                "subject": f"Your Daily Job Matches - {len(jobs)} New Opportunities",
                "html": html_content,
                "text": text_content,
            }

            response = resend.Emails.send(params)

            logger.info(
                "digest_email_sent",
                user_id=str(user.id),
                user_email=user.email,
                job_count=len(jobs),
                email_id=response.get("id"),
            )

            return True

        except resend.exceptions.ResendError as e:
            logger.error(
                "digest_email_failed",
                user_id=str(user.id),
                user_email=user.email,
                error=str(e),
                error_type="resend_error"
            )
            return False
        except Exception as e:
            logger.error(
                "digest_email_failed",
                user_id=str(user.id),
                user_email=user.email,
                error=str(e),
            )
            return False

    @staticmethod
    def send_verification_email(user: "User", verification_token: str) -> bool:
        """
        Send email verification link to user.

        Args:
            user: User object
            verification_token: JWT token for email verification

        Returns:
            bool: True if email sent successfully
        """
        if not resend:
            logger.error("resend_not_installed", user_id=str(user.id))
            return False

        try:
            verification_url = f"{EmailService.BASE_URL}/verify-email?token={verification_token}"

            # Prepare template context
            context = {
                "verification_url": verification_url,
                "base_url": EmailService.BASE_URL,
                "year": datetime.now().year,
            }

            # Render HTML and text templates
            html_content = EmailService._render_template("verification.html", context)
            text_content = f"""
            Welcome to Arbeit!

            Please verify your email address by visiting:
            {verification_url}

            This link will expire in 24 hours.

            If you didn't create an account, you can safely ignore this email.
            """

            params = {
                "from": EmailService.FROM_EMAIL,
                "to": [user.email],
                "subject": "Verify your Arbeit account",
                "html": html_content,
                "text": text_content,
            }

            response = resend.Emails.send(params)

            logger.info(
                "verification_email_sent",
                user_id=str(user.id),
                user_email=user.email,
                email_id=response.get("id"),
            )

            return True

        except resend.exceptions.ResendError as e:
            logger.error(
                "verification_email_failed",
                user_id=str(user.id),
                user_email=user.email,
                error=str(e),
                error_type="resend_error"
            )
            return False
        except Exception as e:
            logger.error(
                "verification_email_failed",
                user_id=str(user.id),
                user_email=user.email,
                error=str(e),
            )
            return False


# Example usage
def test_email_service():
    """Test email service configuration."""
    from app.core.database import SessionLocal

    db = SessionLocal()

    # Get first user
    stmt = select(User).limit(1)
    result = db.execute(stmt)
    user = result.scalar_one_or_none()

    if not user:
        print("No users found in database")
        return False

    # Test jobs data
    test_jobs = [
        {
            "title": "Senior Python Developer",
            "company": "Test Company",
            "location": "Remote",
            "url": "https://example.com/job/1",
            "score": 0.95,
            "salary_min": 100000,
            "salary_max": 150000,
            "remote": True
        }
    ]
    
    # Send digest
    SUCCESS = EmailService.send_digest(user, test_jobs)
    print(f"Email test {'succeeded' if SUCCESS else 'failed'}")
    return SUCCESS