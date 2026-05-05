"""Application service layer.

Services hold the business logic. They sit between the API (which only does
serialization, validation, and HTTP plumbing) and the repositories (which do
storage). A service should never import from ``app.api`` — dependency goes
one way: api -> services -> repositories.
"""
