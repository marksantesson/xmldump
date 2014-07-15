#Copyright 2014 Mark Santesson
#
#   Licensed under the Apache License, Version 2.0 (the "License");
#   you may not use this file except in compliance with the License.
#   You may obtain a copy of the License at
#
#       http://www.apache.org/licenses/LICENSE-2.0
#
#   Unless required by applicable law or agreed to in writing, software
#   distributed under the License is distributed on an "AS IS" BASIS,
#   WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#   See the License for the specific language governing permissions and
#   limitations under the License.


#
# http://www.github.com/marksantesson
#
# The serializable module can save django data to xml format and
# reimport. The intent is that in most cases no customization should
# be required. However, I expect that there are still many cases where
# the code is not yet able to handle the model relationships.
# For instance, I have made no particular effort to implement many to
# many relationships.
#
# To generate xml from the models currently in memory:
#       import serializable
#       xml = serializable.models_to_xml([TopLevelModelClass1, Class2])
#
# The xml that is returned is an instance of the xml.etree.ElmentTree.Element
# class. To display it in a readable format:
#       from xml.dom.minidom import parseString
#       doc = parseString( xml.etree.ElmentTree.tostring(xml) )
#       xml_string = doc.toprettyxml('  ')
#
# In order to delete all the data in memory (in preparation for reloading it,
# presumably):
#       delete_all_models_in_db([TopLevelModelClass1, Class2])
#
# The list of class names that must be passed to the functions need not
# contain all the model classes. They should contain the highest level
# classes only. The module will discover contained classes, whether they
# be models which are referred to by a foreign key, or models which refer
# to the high level model class through a foreign key.
# However, it may be advisable to overload the "owned_models" function
# in order to restrict the default discovery. In some cases it makes
# for a nicer xml nesting if references are not followed all the way
# down.
#
# marksantesson@gmail.com
#


import base64
import copy
import datetime
import dateutil.parser
import itertools
import logging
import re
import sys
from   xml.etree import ElementTree as ET

from   django.db import models
from   django.db.models.fields.related \
                import ReverseManyRelatedObjectsDescriptor
import django.utils.timezone

from   utils import LoggingFilterContext


def _etn(tag, text=None, tail=None, **attribs):
    '''Construct an xml.etree.ElementTree.Element object with the given
    tag, text, tail, and extra attributes.'''
    node = ET.Element(tag, **attribs)
    if text is not None:
        node.text = text
    if tail is not None:
        node.tail = tail
    return node


def _path_to_class(cls):
    return '.'.join( [cls.__module__, cls.__name__] )


def _datetime_to_str(dt):
    vals = list(dt.timetuple()[:6]) + [ dt.microsecond, ]
    return 'datetime(%s%s)' % ( ','.join(map(str,vals))
                              , ',UTC' if dt.tzinfo else '')

def _str_to_datetime(dt):
    # dateutil.parser.parse(datetime.datetime.now().isoformat())
    m=re.match('datetime\(((\d+,){5,6}\d+)(,UTC)?\)',dt)
    assert m
    tzinfo = None if not m.group(3) else django.utils.timezone.utc
    return datetime.datetime( *map(int,m.group(1).split(',')), tzinfo=tzinfo )


def _get_class_from_class_pathname(class_pathname):
    cls_module,cls_name = class_pathname.rsplit('.', 1)
    if cls_module not in sys.modules:
        __import__(cls_module)
    assert cls_name in sys.modules[cls_module].__dict__, \
            '{} not in {}'.format(cls_name, cls_module)

    return sys.modules[cls_module].__dict__[cls_name]


def owned_models(cls, delegate=True):
    '''Return a list of all model classes that have a ForeignKey
    referencing this class. They should not be owned by any other
    objects. Each element returns should be a tuple of the class
    and a function which is passed a model and a QuerySet and
    returns all the models which refer to the model passed in.
    For example, a User might own a Yard:
    (Yard       , lambda self,o: o.get(user__exact=self.id()))
    '''
    if delegate and hasattr(cls, 'owned_models'):
        return cls.owned_models()

    ret = []
    for name in dir(cls):
        if name.endswith('_set'):
            field = getattr(cls, name)
            if field.__class__.__name__=='ReverseManyRelatedObjectsDescriptor':
                raise Exception('implement this')
            elif field.__class__.__name__=='RelatedManager':
                child_cls = field.model
            elif field.__class__.__name__=='ForeignRelatedObjectsDescriptor':
                child_cls = field.related.model
            elif field.__class__.__name__=='ManyRelatedObjectsDescriptor':
                child_cls = field.related.model
            else:
                assert False, 'Do not know how to handle %r.%s %r' % (
                                cls,name,field)
            def f(self, name=name, cls=cls, child_cls=child_cls):
                # I'm not proud of this.
                set_attr = getattr(self,name)
                core_filters = set_attr.core_filters
                assert len(core_filters)==1, '%r %s: %r' % (
                                self, name, core_filters )
                children = list( child_cls.objects.filter(
                                    **{core_filters.keys()[0]:self.pk
                                      }) )
                return children
            ret.append( (child_cls, f) )
    return ret


def models_to_xml(models_to_serialize, include_rest_of_app=True):
    # obj._meta.app_config.models lists all the app models!
    # Just specify root, and this will ensure everything else gets its
    # turn. Might only be for that app... auth is a different one.
    models = copy.copy(models_to_serialize)
    if include_rest_of_app:
        # Add any additional models that are part of the app.
        for model in models_to_serialize:
            newmodels = [ x for x in model._meta.app_config.models.values()
                          if x not in models ]
            models += list(set( newmodels ))
    xml = ET.Element('ModelData')
    context = dict( postprocess = list()
                  , touched     = set()
                  , owned_by    = dict([(cls,None)
                                        for cls in models_to_serialize])
                  )
    for cls in models:
        for o in cls.objects.all():
            if o not in context['touched']:
                node = _model_to_xml(o, context)
                if node is not None:
                    xml.append(node)
    while context['postprocess']:
        x = x['postprocess'].pop(0)
        x(xml, context)
    return  xml


def _model_to_xml(obj, context, delegate=True, name=None):  # obj is an instance
    if obj in context['touched']:
        # Already saved or being saved. Return None or a reference.
        if not name:
            return None # Nothing needed, it isn't a field.
        return _etn( name, type='reference'
                  , to_type=_path_to_class(obj.__class__)
                  , text=repr(obj.pk))
    context['touched'].add(obj)
    if delegate and hasattr(obj, 'to_xml'):
        return obj.to_xml(context, name)

    # Default object serialization.
    valnames = obj._default_manager.values()[0].keys()
    valnames = [ k[:-3] if k.endswith('_id') else k for k in valnames ]

    model_name = _path_to_class( obj.__class__ )
    node = ET.Element(name, type=model_name) if name else ET.Element(model_name)
    for name in valnames:
        value = getattr(obj, name)
        xml = _field_to_xml(obj, name, value, context)
        if xml is not None:
            node.append(xml)

    owned = _etn('___owned')
    for cls,membersFn in owned_models(obj):
        if cls not in context['owned_by']:
            context['owned_by'][cls] = obj.__class__
        elif obj != context['owned_by'][cls]:
            continue
        # Example, (Yard, lambda o: o.get(user__exact=self.id())
        try:
            objs = membersFn(obj)
        except Exception as e:
            if e.__class__.__name__ != 'DoesNotExist':
                raise
            else:
                objs = []
        for owned_obj in objs:
            xml = _model_to_xml(owned_obj, context)
            if xml is not None:
                owned.append( xml )

    if len(owned):
        node.append(owned)

    return node


def _field_to_xml(obj, k, v, context):
    if isinstance(v, models.Model):
        return _model_to_xml(v, context, name=k)
    elif type(v) == int:
        return _etn(k, text=str(v), type=type(v).__name__)
    elif type(v) in (str,unicode) :
        return _etn(k, text=v, type=type(v).__name__)
    elif type(v) == datetime.datetime:
        return _etn( k, text=_datetime_to_str(v), type='datetime')
    elif type(v) == datetime.date:
        return _etn( k, text=str(v), type='date')
    elif type(v) == float:
        return _etn( k, text=str(v), type='float')
    elif type(v) == buffer:
        return _etn( k, text=base64.b64encode(v), type='buffer')
    elif type(v) == bool:
        return _etn(k, text='True' if v else 'False', type='bool')
    raise Exception('Unknown type: {0} {1}'.format(type(v), v))


@LoggingFilterContext.annotate(
        lambda rec: (not isinstance(rec.msg, basestring)) or
                    not (rec.msg.startswith('Deleting') or rec.msg=='Done.')
                    )
def delete_all_models_in_db(root_models):
    '''Delete all object instances from the Django db. The top level
    classes must be passed in, but additional classes will be discovered
    from them.
    '''
    objs = root_models[:]
    i = 0
    while i < len(objs) and i < 10:
        new_objs = list()
        all_models_in_tree(objs[i], new_objs)
        for no in new_objs:
            if no not in objs:
                objs.append(no)
        i += 1
    for obj in objs:
        logging.warn('Deleting %r...', obj)
        obj.objects.all().delete()
    logging.warn('Done.')


def all_models_in_tree(cls, accumulatingList, depth=20, delegate=True):
    '''Generate a list of model classes that are in the tree. This
    is so that they can all be cleared. The list is passed in.'''
    assert depth

    if delegate and hasattr(cls, 'all_models_in_tree'):
        cls.all_models_in_tree(accumulatingList, depth-1)
        return

    if cls in accumulatingList:
        return

    accumulatingList.append( cls )

    for field in cls._meta.fields:
        # This list is explicit until I gain confidence that I have all
        # known field types. Then the "else" can just ignore these types.
        if isinstance(field, (models.fields.AutoField
                             ,models.fields.CharField
                             ,models.fields.TextField
                             ,models.fields.IntegerField
                             ,models.fields.FloatField
                             ,models.fields.DateField
                             ,models.fields.TimeField
                             ,models.fields.DateTimeField
                             ,models.fields.BinaryField
                             ,models.fields.BooleanField
                             )):
            pass
        elif isinstance(field, models.fields.related.ForeignKey):
            # Store just the pk of the related model.
            oclass = field.related.parent_model
            all_models_in_tree(oclass, accumulatingList, depth-1)
        else:
            raise Exception('Field is of unknown type: %r' % ( field, ))
    for model,membersFn in owned_models(cls):
        all_models_in_tree(model, accumulatingList, depth-1)


def xml_to_models(toplevel_xml):
    '''Repopulate the Django db with instances as indicated by the
    xml that is provided.
    '''
    assert isinstance(toplevel_xml, ET.Element)
    context = dict( postprocess  = list()
                  , pp_needs_obj = list()
                  )
    assert toplevel_xml.tag == 'ModelData'
    for obj_xml in toplevel_xml:
        xml_to_model(obj_xml, context)

    while context['postprocess']:
        fn = context['postprocess'].pop(0)
        fn()


def xml_to_model(xml, context, delegate=True):
    '''Only contents and attribs of xml node are used, not tag.
    If delegate is True (the default) it will try to delegate
    processing to the appropriate class's "from_xml" function.
    If False, it will force it to be handled in this function.'''
    assert isinstance(xml, ET.Element)

    context['pp_needs_obj'].append(list())

    class_pathname = xml.get('type', xml.tag)
    cls = _get_class_from_class_pathname(class_pathname)

    if delegate and hasattr(cls, 'from_xml'):
        return cls.from_xml(xml, context)

    attributes_dict = _xml_to_attribs(cls, xml, context)
    obj = cls.objects.create( **attributes_dict )

    pps = context['pp_needs_obj'].pop()
    for pp in pps:
        context['postprocess'].append( lambda: pp(obj) )

    return obj


def _xml_to_attribs(cls, xml, context, delegate=True):
    '''Return a dictionary of all the attributes for an instance of
    this class, as indicated by the xml. Keys preceded by exactly two
    underscores (such as "__version") are presumed to be for
    consumption by the class and are ignored.'''

    if delegate and hasattr(cls, 'xml_to_attribs'):
        return cls.xml_to_attribs(xml, context)

    ret = dict()
    for elem in xml:
        if elem.tag.startswith('__') and not elem.tag.startswith('___'):
            # Ignore this. It is for use by the class's xml_to_attribs.
            # Typically the class will call this function and then
            # modify it based on additional information potentially
            # contained in an entry like this one.
            continue
        typ = elem.get('type')
        if typ is not None:
            assert elem.tag not in ret, \
                    'Found tag name {} listed twice.'.format(elem.tag)
            val = _xml_to_field(elem, context, elem.tag)
            ret[elem.tag] = val
        else:
            assert elem.tag == '___owned'
            # Create post process step for these objects. They will
            # want to look up the object that we're trying to load now.
            for child in elem:
                def fn(child=child, context=context):
                    xml_to_model(child, context)
                context['postprocess'].append( fn )

    return ret


def _xml_to_field(xml, context, fieldname):
    typ = xml.get('type', xml.tag)
    if '.' in typ:
        return xml_to_model(xml, context)
    elif typ == 'int':
        return int(xml.text)
    elif typ == 'str':
        return str(xml.text)
    elif typ == 'unicode':
        return unicode(xml.text)
    elif typ == 'datetime':
        return _str_to_datetime(xml.text)
    elif typ == 'date':
        return datetime.date(*[int(x) for x in xml.text.split('-')])
    elif typ == 'float':
        return float(xml.text)
    elif typ == 'buffer':
        return base64.b64decode(xml.text)
    elif typ == 'bool':
        return {'True':True, 'False':False}[xml.text]
    elif typ == 'reference':
        cls = _get_class_from_class_pathname(xml.get('to_type'))
        kwargs = { cls._meta.pk.attname : int(xml.text) }
        objs = cls.objects.filter(**kwargs)
        assert len(objs) in (0,1)
        if len(objs)==1:
            return objs[0]
        # Try again later.
        def fn(obj, fieldname=fieldname, cls=cls, kwargs=kwargs):
            objs = cls.objects.filter(**kwargs)
            assert len(objs) in (0,1)
            if len(objs)==1:
                setattr(obj, fieldname, objs[0])
            # Still not available. It is probably best that we don't just
            # throw this on the end of the preprocess stack and try again
            # later.
            else:
                raise Exception(('Still could not find object'
                                ' {!r} {!r} to fill out {!r}.{}').format(
                                    cls, kwargs, obj, field_name)
                               )

        context['postprocess'].append( fn )

            # Need some additional context. Which object is being
            # worked on so that I can fixup in the postprocess.
            # Probably need to add fixup fns which take the object and then 
            # at the end of importing I can wrap those with something which
            # passes the object that these attributes are applied to.
            # In extreme cases I may have to create a dummy object until we
            # can load the real one, but we can't guarantee a way out of
            # manual intervention, as a default object may not exist that
            # behaves properly for more than one referent.
            # I'll just support a None for now.

        return None

    raise Exception('Unknown type: {0} {1.tag} {1.text}'.format(typ, xml))
    return _etn(k, type=type(v).__name__, text='NYI')


#class SerializableMixin(object):

#    def to_xml(self, context, name):
#        '''Returns xml that is sufficient to refer to an object of
#        this class. context is a dict which may contain
#        fields that are necessary, such as a post-processing
#        list.'''
#        return model_to_xml(self, context, delegate=False, name=name)

#    @classmethod
#    def owned_models(cls):
#        '''Return a list of all model classes that have a ForeignKey
#        referencing this class. They should not be owned by any other
#        objects. Each element returns should be a tuple of the class
#        and a function which is passed a model and a QuerySet and
#        returns all the models which refer to the model passed in.
#        For example, a User might own a Yard:
#        (Yard       , lambda self,o: o.get(user__exact=self.id()))
#        return owned_models(cls, delegate=False)

#    @classmethod
#    def all_models_in_tree(cls, accumulatingList, depth=20, delegate=True):
#        '''Generate a list of model classes that are in the tree. This
#        is so that they can all be cleared. The list is passed in.'''
#        return all_models_in_tree(cls, accumulatingList, depth, False)

#    @classmethod
#    def from_xml(cls, xml, context):
#        '''Returns a model that is reconstructed from the given xml.
#        context is a dict which may contain
#        fields that are necessary, such as a post-processing
#        list.'''
#        return xml_to_model(xml, context, delegate=False)

#    @classmethod
#    def xml_to_attribs(cls, xml, context):
#        '''Returns a dict of attributes that has been built from the
#        given xml. context is a dict which may contain
#        fields that are necessary, such as a post-processing
#        list. The primary use for this is to take xml from an old
#        version and make to appropriate for use by the current version.'''
#        return xml_to_attribs(xml, context, delegate=False)

