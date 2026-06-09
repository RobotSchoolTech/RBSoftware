from fastapi import APIRouter

from app.api.routes.health import router as health_router
from app.domains.audit.routes import audit_router
from app.domains.auth.routes import auth_router, portal_admin_router, sso_router, users_router
# NOTA (2026-06-09): dominios de comercio/inventario DESMONTADOS.
# RBSoftware es un LMS (educación); pedidos/inventario viven en `robotschool_inventory`.
# catalog, commercial, fulfillment, integrations (webhook WooCommerce SIN auth),
# production e inventory eran código abandonado pero expuesto (0 tráfico en prod).
# El código sigue en app/domains/ pendiente de borrado en un PR aparte.
# Ver vault: [[RobotSchool - RBSoftware LMS Deploy]].
from app.domains.academic.routes.schools import router as schools_router
from app.domains.academic.routes.grades import router as grades_router
from app.domains.academic.routes.courses import router as courses_router
from app.domains.academic.routes.units import router as units_router
from app.domains.academic.routes.materials import router as materials_router
from app.domains.academic.routes.assignments import router as assignments_router
from app.domains.academic.routes.submissions import router as submissions_router
from app.domains.academic.routes.students import router as academic_students_router
from app.domains.rbac.routes import permissions_router, roles_router, user_roles_router
from app.domains.training.routes.programs import router as training_programs_router
from app.domains.training.routes.modules import router as training_modules_router
from app.domains.training.routes.lessons import router as training_lessons_router
from app.domains.training.routes.evaluations import router as training_evaluations_router
from app.domains.training.routes.submissions import router as training_submissions_router
from app.domains.training.routes.enrollments import router as training_enrollments_router
from app.domains.training.routes.certificates import router as training_certificates_router
from app.domains.training.routes.templates import router as training_templates_router
from app.domains.repository.routes.repository import router as repository_router

api_router = APIRouter()
api_router.include_router(health_router, tags=["health"])
api_router.include_router(auth_router)
api_router.include_router(sso_router)
api_router.include_router(portal_admin_router)
api_router.include_router(users_router)
api_router.include_router(roles_router)
api_router.include_router(permissions_router)
api_router.include_router(user_roles_router)
api_router.include_router(audit_router)
api_router.include_router(schools_router)
api_router.include_router(grades_router)
api_router.include_router(courses_router)
api_router.include_router(units_router)
api_router.include_router(materials_router)
api_router.include_router(assignments_router)
api_router.include_router(submissions_router)
api_router.include_router(academic_students_router)
api_router.include_router(training_programs_router)
api_router.include_router(training_modules_router)
api_router.include_router(training_lessons_router)
api_router.include_router(training_evaluations_router)
api_router.include_router(training_submissions_router)
api_router.include_router(training_enrollments_router)
api_router.include_router(training_certificates_router)
api_router.include_router(training_templates_router)
api_router.include_router(repository_router, prefix="/repository", tags=["repository"])
