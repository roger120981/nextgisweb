# -*- coding: utf-8 -*-
from __future__ import division, absolute_import, print_function, unicode_literals

from uuid import uuid4

import pytest
import six
import transaction
from freezegun import freeze_time

from nextgisweb.auth import User
from nextgisweb.core import KindOfData
from nextgisweb.models import DBSession
from nextgisweb.spatial_ref_sys import SRS
from nextgisweb.vector_layer import VectorLayer


class TestKOD1(KindOfData):
    identity = 'test_kod_1'
    display_name = identity


class TestKOD2(KindOfData):
    identity = 'test_kod_2'
    display_name = identity


@pytest.fixture(scope='function', autouse=True)
def prepare_storage(ngw_env):
    with transaction.manager:
        ngw_env.core._clear_storage_tables()

    with ngw_env.core.options.override({'storage.enabled': True}):
        yield


@pytest.fixture(scope='module', autouse=True)
def reset_storage(ngw_env):
    yield
    ngw_env.core.estimate_storage_all()


def test_storage(ngw_env, ngw_webtest_app, ngw_auth_administrator):
    reserve_storage = ngw_env.core.reserve_storage
    with freeze_time() as dt, transaction.manager:
        assert 'storage_reservations' not in DBSession().info

        reserve_storage('test_comp_1', TestKOD1, value_data_volume=100)
        reserve_storage('test_comp_1', TestKOD2, value_data_volume=20)
        reserve_storage('test_comp_2', TestKOD1, value_data_volume=400)
        reserve_storage('test_comp_2', TestKOD2, value_data_volume=80)

        assert 'storage_reservations' in DBSession().info
        assert len(DBSession().info['storage_reservations']) == 4

    assert len(DBSession().info['storage_reservations']) == 0

    cur = ngw_env.core.query_storage()
    assert cur[''] == dict(
        estimated=None, updated=dt(), data_volume=600)
    assert cur[TestKOD1.identity] == dict(
        estimated=None, updated=dt(), data_volume=500)

    res = ngw_webtest_app.get('/api/component/pyramid/storage', status=200)
    assert res.json['']['updated'] == dt().isoformat()
    assert res.json['']['data_volume'] == 600
    assert res.json[TestKOD1.identity]['data_volume'] == 500
    assert res.json[TestKOD2.identity]['data_volume'] == 100


def test_resource_storage(ngw_env, ngw_resource_group, ngw_webtest_app, ngw_auth_administrator):
    reserve_storage = ngw_env.core.reserve_storage
    with transaction.manager:
        res1 = VectorLayer(
            parent_id=ngw_resource_group,
            display_name='test-resource-1',
            owner_user=User.by_keyname('administrator'),
            srs=SRS.filter_by(id=3857).one(),
            geometry_type='POINT',
            tbl_uuid=six.text_type(uuid4().hex),
        ).persist()
        res1.setup_from_fields([])

        res2 = VectorLayer(
            parent_id=ngw_resource_group,
            display_name='test-resource-2',
            owner_user=User.by_keyname('administrator'),
            srs=SRS.filter_by(id=3857).one(),
            geometry_type='POINT',
            tbl_uuid=six.text_type(uuid4().hex),
        ).persist()
        res2.setup_from_fields([])

        reserve_storage('test_comp', TestKOD1, resource=res1, value_data_volume=100)
        reserve_storage('test_comp', TestKOD2, resource=res1, value_data_volume=10)
        reserve_storage('test_comp', TestKOD1, resource=res2, value_data_volume=200)

        DBSession.flush()
        DBSession.expunge(res1)
        DBSession.expunge(res2)

    resp = ngw_webtest_app.get('/api/resource/%d/volume' % res1.id, status=200)
    assert resp.json['volume'] == 110

    resp = ngw_webtest_app.get('/api/resource/%d/volume' % res2.id, status=200)
    assert resp.json['volume'] == 200

    cur = ngw_env.core.query_storage()
    assert cur['']['data_volume'] == 310
    assert cur[TestKOD1.identity]['data_volume'] == 300

    with transaction.manager:
        DBSession.delete(res1)

    cur = ngw_env.core.query_storage()
    assert cur['']['data_volume'] == 200

    with transaction.manager:
        DBSession.delete(res2)

    cur = ngw_env.core.query_storage()
    assert cur['']['data_volume'] == 0
