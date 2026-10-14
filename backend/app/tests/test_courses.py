import pytest
from httpx import AsyncClient

@pytest.mark.asyncio
async def test_courses_workflow(client: AsyncClient):
    # 1. Signup
    signup_data = {"name": "Test User", "email": "test@test.com", "password": "password123"}
    await client.post("/api/auth/signup", json=signup_data)

    # 2. Login
    login_response = await client.post("/api/auth/signin", json={"email": "test@test.com", "password": "password123"})
    token = login_response.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    # 3. Create course
    course_data = {"title": "Test Course", "description": "A test course description"}
    create_response = await client.post("/api/courses/", json=course_data, headers=headers)
    assert create_response.status_code == 201
    course_id = create_response.json()["id"]

    # 4. List courses
    list_response = await client.get("/api/courses/", headers=headers)
    assert list_response.status_code == 200
    assert len(list_response.json()) == 1

    # 5. Get course
    get_response = await client.get(f"/api/courses/{course_id}", headers=headers)
    assert get_response.status_code == 200
    assert get_response.json()["title"] == "Test Course"

    # 6. Update course
    update_data = {"title": "Updated Course"}
    patch_response = await client.patch(f"/api/courses/{course_id}", json=update_data, headers=headers)
    assert patch_response.status_code == 200
    assert patch_response.json()["title"] == "Updated Course"

    # 7. Delete course
    delete_response = await client.delete(f"/api/courses/{course_id}", headers=headers)
    assert delete_response.status_code == 204

    # 8. Verify deletion
    final_list_response = await client.get("/api/courses/", headers=headers)
    assert len(final_list_response.json()) == 0

@pytest.mark.asyncio
async def test_auth_isolation(client: AsyncClient):
    # Setup for User A
    await client.post("/api/auth/signup", json={"name": "A", "email": "a@test.com", "password": "password"})
    token_a = (await client.post("/api/auth/signin", json={"email": "a@test.com", "password": "password"})).json()["access_token"]
    course_a = (await client.post("/api/courses/", json={"title": "Course A"}, headers={"Authorization": f"Bearer {token_a}"})).json()["id"]

    # Setup for User B
    await client.post("/api/auth/signup", json={"name": "B", "email": "b@test.com", "password": "password"})
    token_b = (await client.post("/api/auth/signin", json={"email": "b@test.com", "password": "password"})).json()["access_token"]

    # Attempt list access - should return only user B's courses (empty)
    list_b = await client.get("/api/courses/", headers={"Authorization": f"Bearer {token_b}"})
    assert len(list_b.json()) == 0

    # Attempt direct get access - should 404
    direct_a = await client.get(f"/api/courses/{course_a}", headers={"Authorization": f"Bearer {token_b}"})
    assert direct_a.status_code == 404
