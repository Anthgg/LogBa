import uuid
from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator


class LoginRequest(BaseModel):
    email: str = Field(..., min_length=3, max_length=255)
    password: str = Field(..., min_length=1)

    @field_validator("email")
    @classmethod
    def validate_email_format(cls, v: str) -> str:
        s = v.strip()
        if "@" not in s or "." not in s.split("@")[-1]:
            raise ValueError("Formato de correo electronico invalido.")
        return s.lower()


class CsrfResponse(BaseModel):
    csrf_token: str


class UserCreate(BaseModel):
    organization_id: uuid.UUID
    email: str = Field(..., min_length=3, max_length=255)
    display_name: str = Field(..., min_length=2, max_length=100)
    initial_password: str = Field(..., min_length=12)
    role_codes: List[str] = Field(default_factory=list)
    is_test_data: bool = False

    @field_validator("email")
    @classmethod
    def validate_email_format(cls, v: str) -> str:
        s = v.strip()
        if "@" not in s or "." not in s.split("@")[-1]:
            raise ValueError("Formato de correo electronico invalido.")
        return s.lower()


class UserUpdate(BaseModel):
    display_name: Optional[str] = Field(None, min_length=2, max_length=100)
    password: Optional[str] = Field(None, min_length=12)


class UserRoleAssignRequest(BaseModel):
    role_ids: Optional[List[uuid.UUID]] = None
    role_codes: Optional[List[str]] = None


class UserResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    organization_id: uuid.UUID
    email: str
    display_name: str
    is_active: bool
    is_test_data: bool
    created_at: Optional[datetime] = None
    last_login_at: Optional[datetime] = None
    roles: List[str] = Field(default_factory=list)


class AuthMeResponse(BaseModel):
    user: UserResponse
    organization_id: uuid.UUID
    roles: List[str]
    permissions: List[str]
    mfa_enabled: bool = False


# --- MFA & Step-Up Schemas (F009) ---


class MfaStatusResponse(BaseModel):
    enabled: bool
    methods: List[str] = Field(default_factory=list)
    recovery_codes_remaining: int = 0


class MfaTotpEnrollRequest(BaseModel):
    current_password: str = Field(..., min_length=1)


class MfaTotpEnrollResponse(BaseModel):
    enrollment_id: uuid.UUID
    manual_key: str
    qr_endpoint: str
    otpauth_url: str


class MfaTotpConfirmRequest(BaseModel):
    enrollment_id: uuid.UUID
    code: str = Field(..., min_length=6, max_length=10)


class MfaTotpConfirmResponse(BaseModel):
    status: str = "ACTIVE"
    factor_id: uuid.UUID
    recovery_codes: List[str]


class MfaDisableRequest(BaseModel):
    current_password: str = Field(..., min_length=1)


class MfaRecoveryRegenerateRequest(BaseModel):
    current_password: Optional[str] = None


class MfaRecoveryRegenerateResponse(BaseModel):
    recovery_codes: List[str]


class StepUpRequiredResponse(BaseModel):
    code: str = "STEP_UP_REQUIRED"
    challenge_id: uuid.UUID
    policy: str
    reason: str
    methods: List[str] = Field(default_factory=list)
    expires_at: datetime


class StepUpVerifyRequest(BaseModel):
    challenge_id: uuid.UUID
    method: str = Field(..., description="TOTP or RECOVERY_CODE")
    code: str = Field(..., min_length=6, max_length=32)


class StepUpVerifyResponse(BaseModel):
    status: str = "VERIFIED"
    grant_id: uuid.UUID
    policy_code: str
    expires_at: datetime
