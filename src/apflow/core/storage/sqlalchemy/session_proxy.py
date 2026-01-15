from sqlalchemy.orm import Session
from sqlalchemy.ext.asyncio import AsyncSession

from typing import Any, Union, Optional, Iterable, Sequence, ParamSpec, TypeVar
from sqlalchemy import util
from sqlalchemy.ext.asyncio import AsyncResult, AsyncScalarResult
from sqlalchemy.sql.selectable import ForUpdateParameter

from sqlalchemy.engine import Connection
from sqlalchemy.engine import Engine
from sqlalchemy.engine import Result
from sqlalchemy.engine import ScalarResult
from sqlalchemy.engine.interfaces import _CoreAnyExecuteParams
from sqlalchemy.engine.interfaces import CoreExecuteOptionsParameter

from sqlalchemy.orm._typing import _O
from sqlalchemy.orm._typing import OrmExecuteOptionsParameter
from sqlalchemy.orm.interfaces import ORMOption
from sqlalchemy.orm.session import _BindArguments
from sqlalchemy.orm.session import _EntityBindKey
from sqlalchemy.orm.session import _PKIdentityArgument
from sqlalchemy.orm.session import _SessionBind
from sqlalchemy.sql.base import Executable
from sqlalchemy.sql.elements import ClauseElement


_P = ParamSpec("_P")
_T = TypeVar("_T", bound=Any)


class SqlalchemySessionProxy:
    """
    Database session proxy for handling synchronous and asynchronous SQLAlchemy sessions.
    """

    def __init__(
        self,
        session: Union[Session, AsyncSession],
    ):
        """
        Initialize DatabaseManager with a SQLAlchemy session.

        Args:
            session: SQLAlchemy Session or AsyncSession
        """
        self._session = session
        self._is_async = isinstance(session, AsyncSession)


    @property
    def session(self) -> Union[Session, AsyncSession]:
        """
        Get the underlying SQLAlchemy session.

        Returns:
            The SQLAlchemy Session or AsyncSession.

        """
        return self._session

    @property
    def is_async(self) -> bool:
        """
        Check if the session is asynchronous.

        Returns:
            True if the session is an AsyncSession, False otherwise.
        """
        return self._is_async


    async def refresh(
        self,
        instance: object,
        attribute_names: Optional[Iterable[str]] = None,
        with_for_update: ForUpdateParameter = None,
    ) -> None:
        """
        Refresh the given instance from the database.

        Args:
            instance: The instance to refresh.
        """
        if self.is_async:
            await self._session.refresh(instance, attribute_names=attribute_names, with_for_update=with_for_update)
        else:
            self._session.refresh(instance, attribute_names=attribute_names, with_for_update=with_for_update)



    async def execute(
        self,
        statement: Executable,
        params: Optional[_CoreAnyExecuteParams] = None,
        *,
        execution_options: OrmExecuteOptionsParameter = util.EMPTY_DICT,
        bind_arguments: Optional[_BindArguments] = None,
        **kw: Any,
    ) -> Result[Any]:
        """Execute a statement and return a buffered
        :class:`_engine.Result` object.

        .. seealso::

            :meth:`_orm.Session.execute` - main documentation for execute

        """

        if self.is_async:
            return await self._session.execute(statement, params=params, execution_options=execution_options, bind_arguments=bind_arguments, **kw)
        else:
            return self._session.execute(statement, params=params, execution_options=execution_options, bind_arguments=bind_arguments, **kw)
        

    async def scalars(
        self,
        statement: Executable,
        params: Optional[_CoreAnyExecuteParams] = None,
        *,
        execution_options: OrmExecuteOptionsParameter = util.EMPTY_DICT,
        bind_arguments: Optional[_BindArguments] = None,
        **kw: Any,
    ) -> ScalarResult[Any]:
        """Execute a statement and return scalar results.

        :return: a :class:`_result.ScalarResult` object

        .. versionadded:: 1.4.24 Added :meth:`_asyncio.AsyncSession.scalars`

        .. versionadded:: 1.4.26 Added
           :meth:`_asyncio.async_scoped_session.scalars`

        .. seealso::

            :meth:`_orm.Session.scalars` - main documentation for scalars

            :meth:`_asyncio.AsyncSession.stream_scalars` - streaming version

        """

        if self.is_async:
            return await self._session.scalars(statement, params=params, execution_options=execution_options, bind_arguments=bind_arguments, **kw)
        else:
            return self._session.scalars(statement, params=params, execution_options=execution_options, bind_arguments=bind_arguments, **kw)

    async def get(
        self,
        entity: _EntityBindKey[_O],
        ident: _PKIdentityArgument,
        *,
        options: Optional[Sequence[ORMOption]] = None,
        populate_existing: bool = False,
        with_for_update: ForUpdateParameter = None,
        identity_token: Optional[Any] = None,
        execution_options: OrmExecuteOptionsParameter = util.EMPTY_DICT,
    ) -> Union[_O, None]:
        """Return an instance based on the given primary key identifier,
        or ``None`` if not found.

        .. seealso::

            :meth:`_orm.Session.get` - main documentation for get


        """

        if self.is_async:
            return await self._session.get(
                entity,
                ident,
                options=options,
                populate_existing=populate_existing,
                with_for_update=with_for_update,
                identity_token=identity_token,
                execution_options=execution_options,
            )
        else:
            return self._session.get(
                entity,
                ident,
                options=options,
                populate_existing=populate_existing,
                with_for_update=with_for_update,
                identity_token=identity_token,
                execution_options=execution_options,
            )

    async def get_one(
        self,
        entity: _EntityBindKey[_O],
        ident: _PKIdentityArgument,
        *,
        options: Optional[Sequence[ORMOption]] = None,
        populate_existing: bool = False,
        with_for_update: ForUpdateParameter = None,
        identity_token: Optional[Any] = None,
        execution_options: OrmExecuteOptionsParameter = util.EMPTY_DICT,
    ) -> _O:
        """Return an instance based on the given primary key identifier,
        or raise an exception if not found.

        Raises :class:`_exc.NoResultFound` if the query selects no rows.

        ..versionadded: 2.0.22

        .. seealso::

            :meth:`_orm.Session.get_one` - main documentation for get_one

        """

        if self.is_async:
            return await self._session.get_one(
                entity,
                ident,
                options=options,
                populate_existing=populate_existing,
                with_for_update=with_for_update,
                identity_token=identity_token,
                execution_options=execution_options,
            )
        else: 
            return self._session.get_one(
                entity,
                ident,
                options=options,
                populate_existing=populate_existing,
                with_for_update=with_for_update,
                identity_token=identity_token,
                execution_options=execution_options,
            )

    async def stream(
        self,
        statement: Executable,
        params: Optional[_CoreAnyExecuteParams] = None,
        *,
        execution_options: OrmExecuteOptionsParameter = util.EMPTY_DICT,
        bind_arguments: Optional[_BindArguments] = None,
        **kw: Any,
    ) -> AsyncResult[Any]:
        """Execute a statement and return a streaming
        :class:`_asyncio.AsyncResult` object.

        """
        if self.is_async:
            raise NotImplementedError("Streaming is only supported for asynchronous sessions.")

        return await self._session.stream(
            statement,
            params=params,
            execution_options=execution_options,
            bind_arguments=bind_arguments,
            **kw,
        )

    async def stream_scalars(
        self,
        statement: Executable,
        params: Optional[_CoreAnyExecuteParams] = None,
        *,
        execution_options: OrmExecuteOptionsParameter = util.EMPTY_DICT,
        bind_arguments: Optional[_BindArguments] = None,
        **kw: Any,
    ) -> AsyncScalarResult[Any]:
        """Execute a statement and return a stream of scalar results.

        :return: an :class:`_asyncio.AsyncScalarResult` object

        .. versionadded:: 1.4.24

        .. seealso::

            :meth:`_orm.Session.scalars` - main documentation for scalars

            :meth:`_asyncio.AsyncSession.scalars` - non streaming version

        """

        if self.is_async:
            raise NotImplementedError("Streaming is only supported for asynchronous sessions.")
        
        result = await self.stream_scalars(
            statement,
            params=params,
            execution_options=execution_options,
            bind_arguments=bind_arguments,
            **kw,
        )
        return result.scalars()

    async def delete(self, instance: object) -> None:
        """Mark an instance as deleted.

        The database delete operation occurs upon ``flush()``.

        As this operation may need to cascade along unloaded relationships,
        it is awaitable to allow for those queries to take place.

        .. seealso::

            :meth:`_orm.Session.delete` - main documentation for delete

        """

        if self.is_async:
            await self._session.delete(instance)
        else:
            self._session.delete(instance)

    async def merge(
        self,
        instance: _O,
        *,
        load: bool = True,
        options: Optional[Sequence[ORMOption]] = None,
    ) -> _O:
        """Copy the state of a given instance into a corresponding instance
        within this :class:`_asyncio.AsyncSession`.

        .. seealso::

            :meth:`_orm.Session.merge` - main documentation for merge

        """
        if self.is_async:
            return await self._session.merge( 
                instance, load=load, options=options
            )
        else:
            return self._session.merge( 
                instance, load=load, options=options
            )
        

    async def flush(self, objects: Optional[Sequence[Any]] = None) -> None:
        """Flush all the object changes to the database.

        .. seealso::

            :meth:`_orm.Session.flush` - main documentation for flush

        """

        if self.is_async:
            await self._session.flush()
        else:
            self._session.flush()


    def get_transaction(self) -> Optional[Any]:
        """Return the current root transaction in progress, if any.
        """

        return self._session.get_transaction()


    def get_nested_transaction(self) -> Optional[Any]:
        """Return the current nested transaction in progress, if any.
        """

        return self._session.get_nested_transaction()


    def get_bind(
        self,
        mapper: Optional[_EntityBindKey[_O]] = None,
        clause: Optional[ClauseElement] = None,
        bind: Optional[_SessionBind] = None,
        **kw: Any,
    ) -> Union[Engine, Connection]:
        """Return a "bind" to which the synchronous proxied :class:`_orm.Session`
        is bound.

        Unlike the :meth:`_orm.Session.get_bind` method, this method is
        currently **not** used by this :class:`.AsyncSession` in any way
        in order to resolve engines for requests.
        """

        return self._session.get_bind(
            mapper=mapper, clause=clause, bind=bind, **kw
        )


    async def connection(
        self,
        bind_arguments: Optional[_BindArguments] = None,
        execution_options: Optional[CoreExecuteOptionsParameter] = None,
        **kw: Any,
    ) -> Any:
        """
        This method may also be used to establish execution options for the
        database connection used by the current transaction.
        """

        if self.is_async:
            return await self._session.connection(bind_arguments=bind_arguments, execution_options=execution_options, **kw)
        else:
            return self._session.connection(bind_arguments=bind_arguments, execution_options=execution_options, **kw)


    def begin(self, nested: bool = False) -> Any:
        """
        if is async return an :class:`_asyncio.AsyncSessionTransaction` object.
        else return: the :class:`.SessionTransaction` object.
        """
        if self.is_async:
            return self._session.begin()
        else:
            return self._session.begin(nested=nested)


    def begin_nested(self) -> Any:
        """
        if is async return an :class:`_asyncio.AsyncSessionTransaction` object.
        else return: the :class:`.SessionTransaction` object.
        which will begin a "nested" transaction, e.g. SAVEPOINT.
        """

        return self._session.begin_nested()


    async def rollback(self) -> None:
        """Rollback the current transaction in progress.

        .. seealso::

            :meth:`_orm.Session.rollback` - main documentation for
            "rollback"
        """
        if self.is_async:
            await self._session.rollback()
        else:
            self._session.rollback()


    async def commit(self) -> None:
        """Commit the current transaction in progress.

        .. seealso::

            :meth:`_orm.Session.commit` - main documentation for
            "commit"
        """

        if self.is_async:
            await self._session.commit()
        else:
            self._session.commit()    


    async def close(self) -> None:
        """Close out the transactional resources and ORM objects used by this
        :class:`_asyncio.AsyncSession`.

        .. seealso::

            :meth:`_orm.Session.close` - main documentation for
            "close"
        """
        if self.is_async:
            await self._session.close()
        else:
            self._session.close()

    async def reset(self) -> None:
        """Close out the transactional resources and ORM objects used by this
        :class:`_orm.Session`, resetting the session to its initial state.
        """
        if self.is_async:
            await self._session.reset()
        else:
            self._session.reset()

    async def aclose(self) -> None:
        """A synonym for :meth:`_asyncio.AsyncSession.close`.

        The :meth:`_asyncio.AsyncSession.aclose` name is specifically
        to support the Python standard library ``@contextlib.aclosing``
        context manager function.

        .. versionadded:: 2.0.20

        """
        if not self.is_async:
            raise NotImplementedError(
                "The aclose() method is only available for AsyncSession."
            )
        
        await self._session.aclose()

    async def invalidate(self) -> None:
        """Close this Session, using connection invalidation.

        For a complete description, see :meth:`_orm.Session.invalidate`.
        """
        if self.is_async:
            await self._session.invalidate()
        else:
            self._session.invalidate()


    def add(self, instance: object, _warn: bool = True) -> None:
        r"""Place an object into this :class:`_orm.Session`.

        .. container:: class_bases

            Proxied for the :class:`_orm.Session` class on
            behalf of the :class:`_asyncio.AsyncSession` class.

        Objects that are in the :term:`transient` state when passed to the
        :meth:`_orm.Session.add` method will move to the
        :term:`pending` state, until the next flush, at which point they
        will move to the :term:`persistent` state.

        Objects that are in the :term:`detached` state when passed to the
        :meth:`_orm.Session.add` method will move to the :term:`persistent`
        state directly.

        If the transaction used by the :class:`_orm.Session` is rolled back,
        objects which were transient when they were passed to
        :meth:`_orm.Session.add` will be moved back to the
        :term:`transient` state, and will no longer be present within this
        :class:`_orm.Session`.

        .. seealso::

            :meth:`_orm.Session.add_all`

            :ref:`session_adding` - at :ref:`session_basics`


        """  # noqa: E501

        return self._session.add(instance, _warn=_warn)
    

    def add_all(self, instances: Iterable[object]) -> None:
        r"""Add the given collection of instances to this :class:`_orm.Session`.

        .. container:: class_bases

            Proxied for the :class:`_orm.Session` class on
            behalf of the :class:`_asyncio.AsyncSession` class.

        See the documentation for :meth:`_orm.Session.add` for a general
        behavioral description.

        .. seealso::

            :meth:`_orm.Session.add`

            :ref:`session_adding` - at :ref:`session_basics`


        """  # noqa: E501

        return self._session.add_all(instances)

    def expire(
        self, instance: object, attribute_names: Optional[Iterable[str]] = None
    ) -> None:
        r"""Expire the attributes on an instance.

        .. container:: class_bases

            Proxied for the :class:`_orm.Session` class on
            behalf of the :class:`_asyncio.AsyncSession` class.

        Marks the attributes of an instance as out of date. When an expired
        attribute is next accessed, a query will be issued to the
        :class:`.Session` object's current transactional context in order to
        load all expired attributes for the given instance.   Note that
        a highly isolated transaction will return the same values as were
        previously read in that same transaction, regardless of changes
        in database state outside of that transaction.

        To expire all objects in the :class:`.Session` simultaneously,
        use :meth:`Session.expire_all`.

        The :class:`.Session` object's default behavior is to
        expire all state whenever the :meth:`Session.rollback`
        or :meth:`Session.commit` methods are called, so that new
        state can be loaded for the new transaction.   For this reason,
        calling :meth:`Session.expire` only makes sense for the specific
        case that a non-ORM SQL statement was emitted in the current
        transaction.

        :param instance: The instance to be refreshed.
        :param attribute_names: optional list of string attribute names
          indicating a subset of attributes to be expired.

        .. seealso::

            :ref:`session_expire` - introductory material

            :meth:`.Session.expire`

            :meth:`.Session.refresh`

            :meth:`_orm.Query.populate_existing`


        """  # noqa: E501

        return self._session.expire(instance, attribute_names=attribute_names)

    def expire_all(self) -> None:
        r"""Expires all persistent instances within this Session.

        .. container:: class_bases

            Proxied for the :class:`_orm.Session` class on
            behalf of the :class:`_asyncio.AsyncSession` class.

        When any attributes on a persistent instance is next accessed,
        a query will be issued using the
        :class:`.Session` object's current transactional context in order to
        load all expired attributes for the given instance.   Note that
        a highly isolated transaction will return the same values as were
        previously read in that same transaction, regardless of changes
        in database state outside of that transaction.

        To expire individual objects and individual attributes
        on those objects, use :meth:`Session.expire`.

        The :class:`.Session` object's default behavior is to
        expire all state whenever the :meth:`Session.rollback`
        or :meth:`Session.commit` methods are called, so that new
        state can be loaded for the new transaction.   For this reason,
        calling :meth:`Session.expire_all` is not usually needed,
        assuming the transaction is isolated.

        .. seealso::

            :ref:`session_expire` - introductory material

            :meth:`.Session.expire`

            :meth:`.Session.refresh`

            :meth:`_orm.Query.populate_existing`


        """  # noqa: E501

        return self._proxied.expire_all()

    def expunge(self, instance: object) -> None:
        r"""Remove the `instance` from this ``Session``.

        .. container:: class_bases

            Proxied for the :class:`_orm.Session` class on
            behalf of the :class:`_asyncio.AsyncSession` class.

        This will free all internal references to the instance.  Cascading
        will be applied according to the *expunge* cascade rule.


        """  # noqa: E501

        return self._session.expunge(instance)

    def expunge_all(self) -> None:
        r"""Remove all object instances from this ``Session``.

        .. container:: class_bases

            Proxied for the :class:`_orm.Session` class on
            behalf of the :class:`_asyncio.AsyncSession` class.

        This is equivalent to calling ``expunge(obj)`` on all objects in this
        ``Session``.


        """  # noqa: E501

        return self._session.expunge_all()

    def is_modified(
        self, instance: object, include_collections: bool = True
    ) -> bool:
        r"""Return ``True`` if the given instance has locally
        modified attributes.

        .. container:: class_bases

            Proxied for the :class:`_orm.Session` class on
            behalf of the :class:`_asyncio.AsyncSession` class.

        This method retrieves the history for each instrumented
        attribute on the instance and performs a comparison of the current
        value to its previously flushed or committed value, if any.

        It is in effect a more expensive and accurate
        version of checking for the given instance in the
        :attr:`.Session.dirty` collection; a full test for
        each attribute's net "dirty" status is performed.

        E.g.::

            return session.is_modified(someobject)

        A few caveats to this method apply:

        * Instances present in the :attr:`.Session.dirty` collection may
          report ``False`` when tested with this method.  This is because
          the object may have received change events via attribute mutation,
          thus placing it in :attr:`.Session.dirty`, but ultimately the state
          is the same as that loaded from the database, resulting in no net
          change here.
        * Scalar attributes may not have recorded the previously set
          value when a new value was applied, if the attribute was not loaded,
          or was expired, at the time the new value was received - in these
          cases, the attribute is assumed to have a change, even if there is
          ultimately no net change against its database value. SQLAlchemy in
          most cases does not need the "old" value when a set event occurs, so
          it skips the expense of a SQL call if the old value isn't present,
          based on the assumption that an UPDATE of the scalar value is
          usually needed, and in those few cases where it isn't, is less
          expensive on average than issuing a defensive SELECT.

          The "old" value is fetched unconditionally upon set only if the
          attribute container has the ``active_history`` flag set to ``True``.
          This flag is set typically for primary key attributes and scalar
          object references that are not a simple many-to-one.  To set this
          flag for any arbitrary mapped column, use the ``active_history``
          argument with :func:`.column_property`.

        :param instance: mapped instance to be tested for pending changes.
        :param include_collections: Indicates if multivalued collections
         should be included in the operation.  Setting this to ``False`` is a
         way to detect only local-column based properties (i.e. scalar columns
         or many-to-one foreign keys) that would result in an UPDATE for this
         instance upon flush.


        """  # noqa: E501

        return self._session.is_modified(
            instance, include_collections=include_collections
        )

    def in_transaction(self) -> bool:
        r"""Return True if this :class:`_orm.Session` has begun a transaction.

        .. container:: class_bases

            Proxied for the :class:`_orm.Session` class on
            behalf of the :class:`_asyncio.AsyncSession` class.

        .. versionadded:: 1.4

        .. seealso::

            :attr:`_orm.Session.is_active`



        """  # noqa: E501

        return self._session.in_transaction()

    def in_nested_transaction(self) -> bool:
        r"""Return True if this :class:`_orm.Session` has begun a nested
        transaction, e.g. SAVEPOINT.

        .. container:: class_bases

            Proxied for the :class:`_orm.Session` class on
            behalf of the :class:`_asyncio.AsyncSession` class.

        .. versionadded:: 1.4


        """  # noqa: E501

        return self._session.in_nested_transaction()
