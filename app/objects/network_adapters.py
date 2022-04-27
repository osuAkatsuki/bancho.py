from __future__ import annotations


class OUIEntry:
    def __init__(
        self,
        registry: str,
        assignment: str,
        organization_name: str,
        organization_address: str,
    ) -> None:
        self.registry = registry
        self.assignment = assignment
        self.organization_name = organization_name
        self.organization_address = organization_address
