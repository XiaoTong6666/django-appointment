from django.contrib.auth.password_validation import (
    CommonPasswordValidator, MinimumLengthValidator, NumericPasswordValidator, UserAttributeSimilarityValidator,
)


class ChineseUserAttributeSimilarityValidator(UserAttributeSimilarityValidator):
    def get_error_message(self):
        return '密码与用户的 %(verbose_name)s 过于相似。'

    def get_help_text(self):
        return '密码不能与您的个人信息过于相似。'


class ChineseMinimumLengthValidator(MinimumLengthValidator):
    def get_error_message(self):
        return f'密码太短，至少需要包含 {self.min_length} 个字符。'

    def get_help_text(self):
        return f'密码至少需要包含 {self.min_length} 个字符。'


class ChineseCommonPasswordValidator(CommonPasswordValidator):
    def get_error_message(self):
        return '这个密码太常见。'

    def get_help_text(self):
        return '密码不能使用常见密码。'


class ChineseNumericPasswordValidator(NumericPasswordValidator):
    def get_error_message(self):
        return '密码不能全部由数字组成。'

    def get_help_text(self):
        return '密码不能全部由数字组成。'
