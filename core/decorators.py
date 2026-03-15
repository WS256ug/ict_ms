from django.contrib.auth.decorators import user_passes_test
from django.core.exceptions import PermissionDenied


def admin_required(function):
    """
    Decorator to check if user is admin
    """
    def check_admin(user):
        if user.is_authenticated and user.is_admin:
            return True
        raise PermissionDenied
    
    return user_passes_test(check_admin)(function)


def admin_or_technician_required(function):
    """
    Decorator to check if user is admin or technician
    """
    def check_role(user):
        if user.is_authenticated and (user.is_admin or user.is_technician):
            return True
        raise PermissionDenied
    
    return user_passes_test(check_role)(function)


def department_user_required(function):
    """
    Decorator to check if user is department user
    """
    def check_role(user):
        if user.is_authenticated and user.is_department_user:
            return True
        raise PermissionDenied
    
    return user_passes_test(check_role)(function)