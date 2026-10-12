from whitenoise.storage import CompressedManifestStaticFilesStorage


class ExcelConvertStaticFilesStorage(CompressedManifestStaticFilesStorage):
    # Permite renderizar telas em testes/desenvolvimento antes de collectstatic.
    # O build de produção ainda gera o manifesto e URLs com hash normalmente.
    manifest_strict = False
