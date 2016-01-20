# -*- coding: utf-8 -*-
from __future__ import absolute_import, print_function, unicode_literals

from aldryn_apphooks_config.fields import AppHookConfigField
from cms.models import CMSPlugin
from django.conf import settings as dj_settings
from django.db import models
from django.utils.encoding import force_text, python_2_unicode_compatible
from django.utils.translation import get_language, ugettext_lazy as _
from djangocms_text_ckeditor.fields import HTMLField
from parler.models import TranslatableModel, TranslatedFields
from taggit_autosuggest.managers import TaggableManager

from djangocms_blog.cms_appconfig import BlogConfig
from djangocms_blog.models_abstract import load_model_class
from djangocms_blog.settings import get_setting

BLOG_CURRENT_POST_IDENTIFIER = get_setting('CURRENT_POST_IDENTIFIER')
BLOG_CURRENT_NAMESPACE = get_setting('CURRENT_NAMESPACE')

BLOG_CATEGORY_BASE_MODEL = get_setting('CATEGORY_BASE_MODEL')
BLOG_POST_BASE_MODEL = get_setting('POST_BASE_MODEL')


@python_2_unicode_compatible
class BlogCategory(load_model_class(BLOG_CATEGORY_BASE_MODEL), TranslatableModel):
    """
    Blog category
    """
    translations = TranslatedFields(
        name=models.CharField(_('name'), max_length=255),
        slug=models.SlugField(_('slug'), blank=True, db_index=True),
        meta={'unique_together': (('language_code', 'slug'),)}
    )

    def __str__(self):
        return self.safe_translation_getter('name')


@python_2_unicode_compatible
class Post(load_model_class(BLOG_POST_BASE_MODEL), TranslatableModel):
    """
    Blog post
    """
    translations = TranslatedFields(
        title=models.CharField(_('title'), max_length=255),
        slug=models.SlugField(_('slug'), blank=True, db_index=True),
        abstract=HTMLField(_('abstract'), blank=True, default=''),
        meta_description=models.TextField(verbose_name=_('post meta description'),
                                          blank=True, default=''),
        meta_keywords=models.TextField(verbose_name=_('post meta keywords'),
                                       blank=True, default=''),
        meta_title=models.CharField(verbose_name=_('post meta title'),
                                    help_text=_('used in title tag and social sharing'),
                                    max_length=255,
                                    blank=True, default=''),
        post_text=HTMLField(_('text'), default='', blank=True),
        meta={'unique_together': (('language_code', 'slug'),)}
    )

    def __str__(self):
        return self.safe_translation_getter('title')


class BasePostPlugin(CMSPlugin):
    app_config = AppHookConfigField(
        BlogConfig, null=True, verbose_name=_('app. config'), blank=True
    )

    class Meta:
        abstract = True

    def post_queryset(self, request=None):
        language = get_language()
        posts = Post._default_manager
        if self.app_config:
            posts = posts.namespace(self.app_config.namespace)
        posts = posts.active_translations(language_code=language)
        if not request or not getattr(request, 'toolbar', False) or not request.toolbar.edit_mode:
            posts = posts.published()
        return posts.all()


@python_2_unicode_compatible
class GenericBlogPlugin(BasePostPlugin):
    class Meta:
        abstract = False

    def __str__(self):
        return force_text(_('generic blog plugin'))


@python_2_unicode_compatible
class LatestPostsPlugin(BasePostPlugin):
    latest_posts = models.IntegerField(_('articles'), default=get_setting('LATEST_POSTS'),
                                       help_text=_('The number of latests '
                                                   u'articles to be displayed.'))
    tags = TaggableManager(_('filter by tag'), blank=True,
                           help_text=_('Show only the blog articles tagged with chosen tags.'),
                           related_name='djangocms_blog_latest_post')
    categories = models.ManyToManyField('djangocms_blog.BlogCategory', blank=True,
                                        verbose_name=_('filter by category'),
                                        help_text=_('Show only the blog articles tagged '
                                                    u'with chosen categories.'))

    def __str__(self):
        return force_text(_('%s latest articles by tag') % self.latest_posts)

    def copy_relations(self, oldinstance):
        for tag in oldinstance.tags.all():
            self.tags.add(tag)

    def get_posts(self, request):
        posts = self.post_queryset(request)
        if self.tags.exists():
            posts = posts.filter(tags__in=list(self.tags.all()))
        if self.categories.exists():
            posts = posts.filter(categories__in=list(self.categories.all()))
        return posts.distinct()[:self.latest_posts]


@python_2_unicode_compatible
class AuthorEntriesPlugin(BasePostPlugin):
    authors = models.ManyToManyField(
        dj_settings.AUTH_USER_MODEL, verbose_name=_('authors'),
        limit_choices_to={'djangocms_blog_post_author__publish': True}
    )
    latest_posts = models.IntegerField(
        _('articles'), default=get_setting('LATEST_POSTS'),
        help_text=_('The number of author articles to be displayed.')
    )

    def __str__(self):
        return force_text(_('%s latest articles by author') % self.latest_posts)

    def copy_relations(self, oldinstance):
        self.authors = oldinstance.authors.all()

    def get_posts(self, request):
        posts = self.post_queryset(request)
        return posts[:self.latest_posts]

    def get_authors(self):
        authors = self.authors.all()
        for author in authors:
            author.count = 0
            qs = author.djangocms_blog_post_author
            if self.app_config:
                qs = qs.namespace(self.app_config.namespace)
            count = qs.filter(publish=True).count()
            if count:
                author.count = count
        return authors
