from test_access import project


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
