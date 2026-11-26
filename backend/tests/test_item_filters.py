from datetime import datetime

from test_access import project


def test_list_reports_author_assignee_and_last_change(env):
    _, client, people = env
    admin, member, reader = client('administrator'), client('member'), client('reader')
    path = f'/api/v1/projects/{project(admin)}/items'
    created = member.post(path, json={'title': 'Ticket metadata', 'assignee_id': people['administrator']})
    assert created.status_code == 201, created.text

    item = reader.get(path).json()['items'][0]
    assert item['author'] == {'id': people['member'], 'name': 'member'}
    assert item['assignee']['name'] == 'administrator'
    assert admin.patch(f'/api/v1/items/{item["id"]}', json={'assignee_id': None}).status_code == 200

    updated = reader.get(path).json()['items'][0]
    assert updated['author'] == item['author']
    assert updated['assignee'] is None
    assert datetime.fromisoformat(updated['updated_at']) > datetime.fromisoformat(item['updated_at'])


def test_multiple_statuses_search_counts_and_pagination(env):
    _, client, _ = env
    admin = client('administrator')
    pid = project(admin)
    path = f'/api/v1/projects/{pid}/items'
    for status in ['Open', 'In progress', 'Done', 'Canceled']:
        response = admin.post(path, json={'title': f'Filter {status}', 'status': status})
        assert response.status_code == 201, response.text
    for role in ['administrator', 'reader']:
        c = client(role)
        result = c.get(path, params=[('status', 'Open'), ('status', 'In progress'), ('per_page', '1'), ('sort', 'title')])
        assert result.status_code == 200, result.text
        assert result.json()['total'] == 2
        assert [item['status'] for item in result.json()['items']] == ['In progress']
        result = c.get(path, params=[('status', 'Open'), ('status', 'In progress'), ('per_page', '1'), ('page', '2'), ('sort', 'title')])
        assert [item['status'] for item in result.json()['items']] == ['Open']
        assert c.get(path, params={'status': 'Done'}).json()['total'] == 1
        assert c.get(path).json()['total'] == 4
        assert c.get(path, params=[('status', 'Open'), ('status', 'Done'), ('q', 'Done')]).json()['total'] == 1


def test_filter_validation_and_private_project_isolation(env):
    _, client, _ = env
    admin = client('administrator')
    path = f'/api/v1/projects/{project(admin, "private")}/items'
    filters = [('status', 'Open'), ('status', 'Done'), ('label', 'a'), ('label', 'b')]
    assert client('reader').get(path, params=filters).status_code == 404
    assert admin.get(path, params=[('status', 'Open'), ('status', 'Unknown')]).status_code == 422
    assert admin.get(path, params=[('label', 'valid'), ('label', 'x' * 51)]).status_code == 422


def test_extended_filters_combine_dimensions_and_support_me_and_unassigned(env):
    _, client, people = env
    admin = client('administrator')
    pid = project(admin)
    path = f'/api/v1/projects/{pid}/items'
    for payload in [
        {'title': 'A', 'priority': 'Urgent', 'type': 'Bug', 'assignee_id': people['member']},
        {'title': 'B', 'priority': 'High', 'type': 'Bug'},
        {'title': 'C', 'priority': 'Low', 'type': 'Task', 'assignee_id': people['administrator']},
    ]:
        response = admin.post(path, json=payload)
        assert response.status_code == 201, response.text
    member = client('member')
    result = member.get(path, params=[('priority', 'Urgent'), ('priority', 'High'), ('type', 'Bug'),
                                      ('assignee', 'me'), ('assignee', 'none'), ('sort', 'title')])
    assert result.status_code == 200, result.text
    assert [item['title'] for item in result.json()['items']] == ['A', 'B']
    assert member.get(path, params={'assignee': 'me'}).json()['items'][0]['title'] == 'A'
    assert admin.get(path, params={'assignee': 'me'}).json()['items'][0]['title'] == 'C'
    assert admin.get(path, params={'assignee': people['member']}).json()['total'] == 1
    for key, value in [('priority', 'Critical'), ('type', 'Epic'), ('assignee', 'invalid'), ('direction', 'invalid')]:
        assert admin.get(path, params={key: value}).status_code == 422


def test_sort_direction_priority_and_null_due_dates_with_pagination(env):
    _, client, _ = env
    admin = client('administrator')
    path = f'/api/v1/projects/{project(admin)}/items'
    for title, priority, due_date in [('B', 'Low', None), ('A', 'Urgent', '2026-11-01'), ('C', 'High', '2026-12-01')]:
        response = admin.post(path, json={'title': title, 'priority': priority, 'due_date': due_date})
        assert response.status_code == 201, response.text
    def titles(**params):
        result = admin.get(path, params=params)
        assert result.status_code == 200, result.text
        return [item['title'] for item in result.json()['items']]
    assert titles(sort='priority') == ['A', 'C', 'B']
    assert titles(sort='priority', direction='asc') == ['B', 'C', 'A']
    assert titles(sort='due_date') == ['A', 'C', 'B']
    assert titles(sort='due_date', direction='desc') == ['C', 'A', 'B']
    assert titles(sort='title', direction='desc', per_page=1, page=2) == ['B']


def test_assignee_filter_options_respect_project_access_and_include_historical_assignees(env):
    _, client, people = env
    admin = client('administrator')
    pid = project(admin)
    private_pid = project(admin, 'private', key='SEC')
    for project_id, person in [(pid, people['member']), (private_pid, people['administrator'])]:
        response = admin.post(f'/api/v1/projects/{project_id}/items', json={'title': 'Assigned', 'assignee_id': person})
        assert response.status_code == 201, response.text
    response = client('reader').get(f'/api/v1/projects/{pid}/item-assignees')
    assert response.status_code == 200
    assert [person['id'] for person in response.json()] == [people['member']]
    assert admin.delete(f'/api/v1/projects/{pid}/members/{people["member"]}').status_code == 200
    assert [person['id'] for person in client('reader').get(f'/api/v1/projects/{pid}/item-assignees').json()] == [people['member']]
    assert client('reader').get(f'/api/v1/projects/{private_pid}/item-assignees').status_code == 404
    assert client('member').get(f'/api/v1/projects/{pid}/items', params={'assignee': 'me'}).status_code == 404
