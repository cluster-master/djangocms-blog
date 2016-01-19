# -*- coding: utf-8 -*-
from __future__ import absolute_import, print_function, unicode_literals

from aldryn_apphooks_config.fields import AppHookConfigField
from aldryn_apphooks_config.managers.parler import AppHookConfigTranslatableManager
from cms.models import PlaceholderField
from django.conf import settings as dj_settings
from django.core.urlresolvers import reverse
from django.db import models
from django.utils import timezone
from django.utils.encoding import force_text
from django.utils.html import escape, strip_tags
from django.utils.text import slugify
from django.utils.translation import get_language, ugettext_lazy as _
from filer.fields.image import FilerImageField
from meta_mixin.models import ModelMeta
from taggit_autosuggest.managers import TaggableManager

from djangocms_blog.cms_appconfig import BlogConfig
from djangocms_blog.managers import GenericDateTaggedManager
from djangocms_blog.settings import get_setting

BLOG_CURRENT_POST_IDENTIFIER = get_setting('CURRENT_POST_IDENTIFIER')
BLOG_CURRENT_NAMESPACE = get_setting('CURRENT_NAMESPACE')


class AbstractBlogCategory(models.Model):
    """
    Blog category
    """
    parent = models.ForeignKey('self', verbose_name=_('parent'), null=True, blank=True)
    date_created = models.DateTimeField(_('created at'), auto_now_add=True)
    date_modified = models.DateTimeField(_('modified at'), auto_now=True)
    app_config = AppHookConfigField(
        BlogConfig, null=True, verbose_name=_('app. config')
    )

    objects = AppHookConfigTranslatableManager()

    class Meta:
        abstract = True
        verbose_name = _('blog category')
        verbose_name_plural = _('blog categories')

    @property
    def count(self):
        return self.blog_posts.namespace(self.app_config.namespace).published().count()

    def get_absolute_url(self, lang=None):
        if not lang:
            lang = get_language()
        if self.has_translation(lang, ):
            slug = self.safe_translation_getter('slug', language_code=lang)
            return reverse(
                '%s:posts-category' % self.app_config.namespace,
                kwargs={'category': slug},
                current_app=self.app_config.namespace
            )
        # in case category doesn't exist in this language, gracefully fallback
        # to posts-latest
        return reverse(
            '%s:posts-latest' % self.app_config.namespace, current_app=self.app_config.namespace
        )

    def save(self, *args, **kwargs):
        super(AbstractBlogCategory, self).save(*args, **kwargs)
        for lang in self.get_available_languages():
            self.set_current_language(lang)
            if not self.slug and self.name:
                self.slug = slugify(force_text(self.name))
        self.save_translations()


class AbstractPost(ModelMeta, models.Model):
    """
    Blog post
    """
    author = models.ForeignKey(dj_settings.AUTH_USER_MODEL,
                               verbose_name=_('author'), null=True, blank=True,
                               related_name='djangocms_blog_post_author')

    date_created = models.DateTimeField(_('created'), auto_now_add=True)
    date_modified = models.DateTimeField(_('last modified'), auto_now=True)
    date_published = models.DateTimeField(_('published since'),
                                          default=timezone.now)
    date_published_end = models.DateTimeField(_('published until'), null=True,
                                              blank=True)
    publish = models.BooleanField(_('publish'), default=False)
    categories = models.ManyToManyField('djangocms_blog.BlogCategory', verbose_name=_('category'),
                                        related_name='blog_posts', )
    main_image = FilerImageField(verbose_name=_('main image'), blank=True, null=True,
                                 on_delete=models.SET_NULL,
                                 related_name='djangocms_blog_post_image')
    main_image_thumbnail = models.ForeignKey('cmsplugin_filer_image.ThumbnailOption',
                                             verbose_name=_('main image thumbnail'),
                                             related_name='djangocms_blog_post_thumbnail',
                                             on_delete=models.SET_NULL,
                                             blank=True, null=True)
    main_image_full = models.ForeignKey('cmsplugin_filer_image.ThumbnailOption',
                                        verbose_name=_('main image full'),
                                        related_name='djangocms_blog_post_full',
                                        on_delete=models.SET_NULL,
                                        blank=True, null=True)
    enable_comments = models.BooleanField(verbose_name=_('enable comments on post'),
                                          default=get_setting('ENABLE_COMMENTS'))
    sites = models.ManyToManyField('sites.Site', verbose_name=_('Site(s)'), blank=True,
                                   help_text=_('Select sites in which to show the post. '
                                               'If none is set it will be '
                                               'visible in all the configured sites.'))
    app_config = AppHookConfigField(
        BlogConfig, null=True, verbose_name=_('app. config')
    )

    content = PlaceholderField('post_content', related_name='post_content')

    objects = GenericDateTaggedManager()
    tags = TaggableManager(blank=True, related_name='djangocms_blog_tags')

    _metadata = {
        'title': 'get_title',
        'description': 'get_description',
        'keywords': 'get_keywords',
        'og_description': 'get_description',
        'twitter_description': 'get_description',
        'gplus_description': 'get_description',
        'locale': 'get_locale',
        'image': 'get_image_full_url',
        'object_type': 'get_meta_attribute',
        'og_type': 'get_meta_attribute',
        'og_app_id': 'get_meta_attribute',
        'og_profile_id': 'get_meta_attribute',
        'og_publisher': 'get_meta_attribute',
        'og_author_url': 'get_meta_attribute',
        'og_author': 'get_meta_attribute',
        'twitter_type': 'get_meta_attribute',
        'twitter_site': 'get_meta_attribute',
        'twitter_author': 'get_meta_attribute',
        'gplus_type': 'get_meta_attribute',
        'gplus_author': 'get_meta_attribute',
        'published_time': 'date_published',
        'modified_time': 'date_modified',
        'expiration_time': 'date_published_end',
        'tag': 'get_tags',
        'url': 'get_absolute_url',
    }

    class Meta:
        abstract = True
        verbose_name = _('blog article')
        verbose_name_plural = _('blog articles')
        ordering = ('-date_published', '-date_created')
        get_latest_by = 'date_published'

    def get_absolute_url(self, lang=None):
        if not lang:
            lang = get_language()
        category = self.categories.first()
        kwargs = {}
        urlconf = get_setting('PERMALINK_URLS')[self.app_config.url_patterns]
        if '<year>' in urlconf:
            kwargs['year'] = self.date_published.year
        if '<month>' in urlconf:
            kwargs['month'] = '%02d' % self.date_published.month
        if '<day>' in urlconf:
            kwargs['day'] = '%02d' % self.date_published.day
        if '<slug>' in urlconf:
            kwargs['slug'] = self.safe_translation_getter('slug', language_code=lang, any_language=True)  # NOQA
        if '<category>' in urlconf:
            kwargs['category'] = category.safe_translation_getter('slug', language_code=lang, any_language=True)  # NOQA
        return reverse('%s:post-detail' % self.app_config.namespace, kwargs=kwargs)

    def get_meta_attribute(self, param):
        """
        Retrieves django-meta attributes from apphook config instance
        :param param: django-meta attribute passed as key
        """
        attr = None
        value = getattr(self.app_config, param)
        if value:
            attr = getattr(self, value, None)
        if attr is not None:
            if callable(attr):
                try:
                    data = attr(param)
                except TypeError:
                    data = attr()
            else:
                data = attr
        else:
            data = value
        return data

    def save_translation(self, translation, *args, **kwargs):
        if not translation.slug and translation.title:
            translation.slug = slugify(translation.title)
        super(AbstractPost, self).save_translation(translation, *args, **kwargs)

    def get_title(self):
        title = self.safe_translation_getter('meta_title', any_language=True)
        if not title:
            title = self.safe_translation_getter('title', any_language=True)
        return title.strip()

    def get_keywords(self):
        return self.safe_translation_getter('meta_keywords').strip().split(',')

    def get_locale(self):
        return self.get_current_language()

    def get_description(self):
        description = self.safe_translation_getter('meta_description', any_language=True)
        if not description:
            description = self.safe_translation_getter('abstract', any_language=True)
        return escape(strip_tags(description)).strip()

    def get_image_full_url(self):
        if self.main_image:
            return self.make_full_url(self.main_image.url)
        return ''

    def get_tags(self):
        taglist = [tag.name for tag in self.tags.all()]
        return ','.join(taglist)

    def get_author(self):
        return self.author

    def thumbnail_options(self):
        if self.main_image_thumbnail_id:
            return self.main_image_thumbnail.as_dict
        else:
            return get_setting('IMAGE_THUMBNAIL_SIZE')

    def full_image_options(self):
        if self.main_image_full_id:
            return self.main_image_full.as_dict
        else:
            return get_setting('IMAGE_FULL_SIZE')

    def get_full_url(self):
        return self.make_full_url(self.get_absolute_url())
