from prf.tests.prf_testcase import PrfTestCase
import prf
import prf.mongodb
import prf.dataset
from prf.dataset import (
    get_dataset_names, define_document, load_documents, get_document,
    set_document, get_namespaces, namespace_storage_module, get_document_meta
)


class TestDataset(PrfTestCase):
    def setUp(self):
        super(TestDataset, self).setUp()
        self.drop_databases()
        self.unload_documents()

    def drop_databases(self):
        c = prf.mongodb.mongo.connection.get_connection()
        c.drop_database(self.conf.registry.settings.get('mongodb.db'))
        for namespace in get_namespaces():
            if namespace != 'default':
                c.drop_database(namespace)

    def unload_documents(self):
        for ns in ['default', 'prftest2']:
            if hasattr(prf.dataset, ns):
                delattr(prf.dataset, ns)

    def create_collection(self, namespace, name):
        cls = define_document(name, namespace=namespace)
        # Create a document and delete it to make sure the collection exists
        cls(name='hello').save().delete()
        return cls

    def test_get_dataset_names(self):
        self.create_collection('default', 'col1')
        self.create_collection('default', 'col2')
        self.create_collection('prf-test2', 'col3')
        assert get_dataset_names() == [
            ['default', 'col1', 'col1'],
            ['default', 'col2', 'col2'],
            ['prf-test2', 'col3', 'col3'],
        ]

    def test_get_dataset_names_only(self):
        self.create_collection('default', 'col1')
        self.create_collection('default', 'col2')
        self.create_collection('prf-test2', 'col3')
        assert get_dataset_names(only_namespace="prf-test2") == [
            ['prf-test2', 'col3', 'col3'],
        ]

    def test_load_documents(self):
        self.create_collection('default', 'col1')
        self.create_collection('prf-test2', 'col2')
        load_documents()
        assert hasattr(prf.dataset, 'default')
        assert hasattr(prf.dataset.default, 'col1')
        assert hasattr(prf.dataset, 'prftest2')
        assert hasattr(prf.dataset.prftest2, 'col2')

    def test_get_document_raises(self):
        self.assertRaises(AttributeError, lambda: get_document('default', 'col1'))
        cls = get_document('default', 'col1', _raise=False)
        assert cls is None

    def test_get_document(self):
        self.create_collection('prf-test2', 'col1')
        load_documents()
        cls = get_document('prf-test2', 'col1')
        assert cls is not None

    def test_namespace_storage_module_raises(self):
        self.assertRaises(
            AttributeError,
            lambda: namespace_storage_module('namespace_storage_module', _set=True)
        )

    def test_get_document_meta(self):
        assert not get_document_meta('default', 'col1')
        self.create_collection('default', 'col1')
        meta = get_document_meta('default', 'col1')
        assert meta['db_alias'] == 'default'
        assert meta['_cls'] == 'col1'
        assert meta['collection'] == 'col1'

    def test_define_document(self):
        cls = self.create_collection('default', 'col1')
        d = define_document('col1', namespace='default')
        assert cls != d
        assert d._meta['db_alias'] == 'default'

        set_document('default', 'col1', cls)
        d = define_document('col1', namespace='default')
        assert cls == d

        d = define_document('col1', namespace='default', redefine=True)
        assert cls != d
