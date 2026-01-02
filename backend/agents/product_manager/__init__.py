"""
Product Manager Agent Module - Part 14

This module provides autonomous product management capabilities that transform
Navi from a coding assistant into a complete Product Manager.
"""

from .product_manager_agent import (
    ProductManagerAgent,
    ProductManagerService,
    ProductRequirementsDocument,
    UserStory,
    Requirement,
    TechnicalDesign,
    EngineeringTask,
    Priority,
    TaskType
)

__all__ = [
    'ProductManagerAgent',
    'ProductManagerService', 
    'ProductRequirementsDocument',
    'UserStory',
    'Requirement',
    'TechnicalDesign',
    'EngineeringTask',
    'Priority',
    'TaskType'
]