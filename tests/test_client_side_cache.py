import asyncio

import pytest

from cashews.backends.memory import Memory

pytestmark = [pytest.mark.asyncio, pytest.mark.redis]


@pytest.fixture(name="create_cache")
def _create_cache(redis_dsn, backend_factory):
    from cashews.backends.redis.client_side import BcastClientSide

    def call(local_cache):
        return backend_factory(BcastClientSide, redis_dsn, hash_key=None, local_cache=local_cache)

    return call


async def test_set_get_bcast(create_cache):
    cachef_local = Memory()
    cachef = await create_cache(cachef_local)
    caches_local = Memory()
    caches = await create_cache(caches_local)

    await cachef.set("cashews", b"value", expire=0.1)
    await asyncio.sleep(0.01)  # skip init signal about invalidation
    assert await cachef.get("cashews") == b"value"
    assert await caches.get("cashews") == b"value"
    assert await cachef_local.get("cashews") == b"value"
    assert await caches_local.get("cashews") == b"value"
    await asyncio.sleep(0.2)
    assert await cachef_local.get("cashews") is None
    assert await caches_local.get("cashews") is None

    assert await caches.get("cashews") is None

    await caches.close()
    await cachef.close()


async def test_set_none_bcast(create_cache):
    cachef_local = Memory()
    cachef = await create_cache(cachef_local)
    caches_local = Memory()
    caches = await create_cache(caches_local)

    assert await caches.get("key") is None
    assert not await caches.exists("key")
    assert await caches_local.exists("key")
    assert await caches.get("key") is None

    await cachef.set("key", None, expire=10000)
    await asyncio.sleep(0.01)  # skip init signal about invalidation
    assert await cachef.exists("key")
    assert await cachef_local.exists("key")

    assert await caches.get("key") is None
    assert await caches.exists("key")
    assert await caches_local.exists("key")

    await caches.close()
    await cachef.close()


async def test_del_bcast(create_cache):
    cachef_local = Memory()
    cachef = await create_cache(cachef_local)
    caches_local = Memory()
    caches = await create_cache(caches_local)

    await cachef.set("key", b"value")
    await asyncio.sleep(0.05)  # skip init signal about invalidation

    assert await cachef.get("key") == b"value"
    assert await caches.get("key") == b"value"
    await cachef.delete("key")
    await asyncio.sleep(0.05)  # skip init signal about invalidation
    assert await caches.get("key") is None


async def test_rewrite_bcast(create_cache):
    cachef_local = Memory()
    cachef = await create_cache(cachef_local)
    caches_local = Memory()
    caches = await create_cache(caches_local)

    await cachef.set("key", b"value")
    await asyncio.sleep(0.05)  # skip init signal about invalidation

    assert await cachef.get("key") == b"value"
    assert await caches.get("key") == b"value"

    await caches.set("key", b"new", expire=0.1)
    await asyncio.sleep(0.05)  # skip init signal about invalidation

    assert await cachef.get("key") == b"new"

    await asyncio.sleep(0.15)
    assert await caches.get("key") is None
    assert await cachef.get("key") is None

    assert await cachef.incr("key") == 1
    assert await caches.incr("key") == 2

    await caches.close()
    await cachef.close()


async def test_simple_cmd_bcast_many(create_cache):
    from cashews.backends.redis.client_side import _empty_in_redis

    local = Memory()
    cache = await create_cache(local)
    await cache.set("key:1", "test")
    await cache.set("key:2", "test2")

    await cache.get("key:1")
    assert await local.get("key:1") == "test"

    assert await cache.get_many("key:1", "key:2", "key:3") == ("test", "test2", None)
    assert await local.get("key:2") == "test2"
    assert await local.get("key:3") is _empty_in_redis

    async for key in cache.scan("key:*"):
        assert key in ("key:1", "key:2")
        break
    else:
        assert False

    async for key, value in cache.get_match("key:*"):
        assert key in ("key:1", "key:2")
        assert value in ("test", "test2")
        break
    else:
        assert False

    await local.clear()

    assert await cache.get_many("key:1", "key:3") == ("test", None)

    async for key in cache.scan("key:*"):
        assert key in ("key:1", "key:2")

    async for key, value in cache.get_match("key:*"):
        assert key in ("key:1", "key:2")
        assert value in ("test", "test2")

    assert await local.get("key:1") == "test"

    await cache.delete_match("key:*")
    assert await cache.get("key:1") is None
    assert await local.get("key:1") is _empty_in_redis

    async for _ in cache.scan("key:*"):
        assert False

    async for _ in cache.get_match("key:*"):
        assert False

    await cache.close()
