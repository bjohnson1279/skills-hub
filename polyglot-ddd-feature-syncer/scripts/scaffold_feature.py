import os
import sys
import argparse

def generate_feature_checklist(feature_name):
    print(f"=== Polyglot DDD Feature Checklist: {feature_name} ===")
    print("1. [ ] Update GraphQL Prisma schema: gql-ddd-inventory/prisma/schema.prisma")
    print("2. [ ] Update Express Prisma schema: js-ddd-inventory/prisma/schema.prisma")
    print("3. [ ] Add PHP Postgres DDL: php-ddd-inventory/docker/postgres/init/")
    print("4. [ ] Create Domain Entity in GraphQL: gql-ddd-inventory/src/domain/entities/")
    print("5. [ ] Create Domain Entity in JS: js-ddd-inventory/src/domain/")
    print("6. [ ] Create Domain Entity in PHP: php-ddd-inventory/src/Domain/")
    print("7. [ ] Add GraphQL typeDefs and Resolvers: gql-ddd-inventory/src/infrastructure/graphql/")
    print("8. [ ] Add Express REST Routes: js-ddd-inventory/src/index.ts")
    print("9. [ ] Add PHP REST Handlers: php-ddd-inventory/public/index.php")
    print("10.[ ] Add React Client Panel: react-ddd-inventory-client/src/components/Panels.tsx")
    print("11.[ ] Add Jest & PHPUnit Unit Tests")

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description="Polyglot DDD Feature Scaffolder")
    parser.add_argument("--feature", type=str, default="NewFeature", help="Name of feature to scaffold")
    args = parser.parse_args()
    generate_feature_checklist(args.feature)
