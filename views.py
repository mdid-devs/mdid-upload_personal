from __future__ import with_statement
import mimetypes
import os
import chromelogger as console
from settings import RESTRICT_TO_DEFAULTS, DEFAULT_PERSONAL_COLLECTION, DEFAULT_PERSONAL_STORAGE

from django.conf import settings
from django import forms
from django.core.urlresolvers import resolve, reverse
from django.http import HttpResponse, Http404, HttpResponseRedirect, HttpResponseNotAllowed, HttpResponseServerError, HttpResponseForbidden
from django.forms.util import ErrorList
from django.shortcuts import _get_queryset, get_object_or_404, get_list_or_404, render_to_response
from django.contrib.auth.decorators import login_required
from django.views.decorators.csrf import csrf_exempt
from django.template import RequestContext
from django.template.loader import render_to_string
from django.utils import simplejson

from rooibos.storage.models import Media, Storage
from rooibos.data.models import Collection, Record, Field, FieldValue, CollectionItem, standardfield
from rooibos.storage import get_media_for_record, get_image_for_record, get_thumbnail_for_record, match_up_media, analyze_media, analyze_records, find_record_by_identifier
from rooibos.access import filter_by_access
from rooibos.storage.views import make_storage_select_choice


@csrf_exempt
@login_required
def import_personal_files(request):
    available_storage = get_list_or_404(filter_by_access(request.user, Storage, write=True).order_by('title'))
    available_collections = get_list_or_404(filter_by_access(request.user, Collection))
    writable_collection_ids = list(filter_by_access(request.user, Collection, write=True).values_list('id', flat=True))

    storage_choices = choices = [make_storage_select_choice(s, request.user) for s in available_storage]

    # if DEFAULT_PERSONAL_COLLECTION and RESTRICT_TO_DEFAULTS:
    #     available_collections = DEFAULT_PERSONAL_COLLECTION
    #
    # if DEFAULT_PERSONAL_STORAGE and RESTRICT_TO_DEFAULTS:
    #     available_storage = DEFAULT_PERSONAL_STORAGE

    class UploadFileForm(forms.Form):
        collection = forms.ChoiceField(choices=((c.id,
                                                 '%s%s' % ('*' if c.id in writable_collection_ids else '',
                                                           c.title)) for c in sorted(available_collections,
                                                                                     key=lambda c: c.title)))
        storage = forms.ChoiceField(choices=storage_choices)
        file = forms.FileField()
        create_records = forms.BooleanField(required=False)
        replace_files = forms.BooleanField(required=False, label='Replace files of same type')
        multiple_files = forms.BooleanField(required=False,
                                           label='Allow multiple files of same type')
        personal_records = forms.BooleanField(required=False)

        def clean(self):
            cleaned_data = self.cleaned_data
            if any(self.errors):
                return cleaned_data
            # personal = cleaned_data['personal_records']
            # if not personal and not int(cleaned_data['collection']) in writable_collection_ids:
            #     self._errors['collection'] = ErrorList(["Can only add personal records to selected collection"])
            #     del cleaned_data['collection']
            return cleaned_data
    console.log(request.method)
    if request.method == 'POST':
        # get the form and check that it's valid
        form = UploadFileForm(request.POST, request.FILES)
        if form.is_valid():
        # get settings from form data

            create_records = True
            replace_files = True
            multiple_files = True
            personal_records = True

            collection = get_object_or_404(
                filter_by_access(request.user,
                                 Collection.objects.filter(
                                     id=form.cleaned_data['collection']), write=None))
            storage = get_object_or_404(
                filter_by_access(request.user, Storage.objects.filter(id=form.cleaned_data['storage'].split(',')[0]),
                                 write=True))
            file = request.FILES['file']
            console.log(file)
            record = None

            limit = storage.get_upload_limit(request.user)
            if limit > 0 and file.size > limit * 1024:
                result = "The uploaded file is too large (%d>%d)." % (file.size, limit * 1024)
            else:

                mimetype = mimetypes.guess_type(file.name)[0] or file.content_type

                owner = request.user
                #if personal_records else None
                id = os.path.splitext(file.name)[0]

                # find record by identifier
                titlefield = standardfield('title')
                idfield = standardfield('identifier')

                # Match identifiers that are either full file name (with extension) or just base name match
                records = find_record_by_identifier((id, file.name,),
                                                    collection,
                                                    owner=owner,
                                                    ignore_suffix=multiple_files)
                result = "File skipped."

                if len(records) == 1:
                    # Matching record found
                    record = records[0]
                    media = record.media_set.filter(storage=storage, mimetype=mimetype)
                    media_same_id = media.filter(name=id)
                    if len(media) == 0 or (len(media_same_id) == 0 and multiple_files):
                        # No media yet
                        media = Media.objects.create(record=record,
                                                     name=id,
                                                     storage=storage,
                                                     mimetype=mimetype)
                        media.save_file(file.name, file)
                        result = "File added (Identifier '%s')." % id
                    elif len(media_same_id) > 0 and multiple_files:
                        # Replace existing media with same name and mimetype
                        media = media_same_id[0]
                        media.delete_file()
                        media.save_file(file.name, file)
                        result = "File replaced (Identifier '%s')." % id
                    elif replace_files:
                        # Replace existing media with same mimetype
                        media = media[0]
                        media.delete_file()
                        media.save_file(file.name, file)
                        result = "File replaced (Identifier '%s')." % id
                    else:
                        result = "File skipped, media files already attached."
                elif len(records) == 0:
                    # No matching record found
                    if create_records:
                        # Create a record
                        record = Record.objects.create(name=id, owner=owner)
                        CollectionItem.objects.create(collection=collection, record=record)
                        FieldValue.objects.create(record=record, field=idfield, value=id, order=0)
                        FieldValue.objects.create(record=record, field=titlefield, value=id, order=1)
                        media = Media.objects.create(record=record,
                                                     name=id,
                                                     storage=storage,
                                                     mimetype=mimetype)
                        media.save_file(file.name, file)
                        result = "File added to new record (Identifier '%s')." % id
                    else:
                        result = "File skipped, no matching record found (Identifier '%s')." % id
                else:
                    result = "File skipped, multiple matching records found (Identifier '%s')." % id
                    # Multiple matching records found
                    pass

            if request.POST.get('swfupload') == 'true':
                html = render_to_string('storage_import_file_response.html',
                                        {'result': result,
                                         'record': record, },
                                        context_instance=RequestContext(request)
                )
                return HttpResponse(content=simplejson.dumps(dict(status='ok', html=html)),
                                    mimetype='application/json')

            request.user.message_set.create(message=result)
            next = request.GET.get('next', request.get_full_path())
            return HttpResponseRedirect(next)

        else:
            # invalid form submission
            if request.POST.get('swfupload') == 'true':
                html = render_to_string('storage_import_file_response.html',
                                        {'result': form.errors},
                                        context_instance=RequestContext(request)
                )
                console.log(html)
                return HttpResponse(content=simplejson.dumps(dict(status='ok', html=html)),
                                    mimetype='application/json')

    else:
        form = UploadFileForm()
        console.log(form)

    return render_to_response('import_personal_files.html',
                              {'upload_form': form,
                              },
                              context_instance=RequestContext(request))